"""`sdetkit mcp`: verify_change and gate_fast for coding agents, over MCP on stdio."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sdetkit import change_verifier, mcp_server

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "calc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "calc" / "__init__.py").write_text(BUGGY, encoding="utf-8")
    (repo / "tests" / "test_zero.py").write_text(
        "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n", encoding="utf-8"
    )
    (repo / "pyproject.toml").write_text('[project]\nname = "calc"\nversion = "0"\n')
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _uncommitted_fix(repo: Path) -> None:
    """What an agent leaves behind: a modified file and a new, untracked test."""

    (repo / "src" / "calc" / "__init__.py").write_text(FIXED, encoding="utf-8")
    (repo / "tests" / "test_add.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )


def _call(server: mcp_server.Server, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None and "result" in response, response
    return response["result"]


def test_initialize_negotiates_the_protocol_version() -> None:
    server = mcp_server.Server(cwd=Path.cwd())

    known = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }
    )
    unknown = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "1999-01-01"},
        }
    )

    assert known is not None and known["result"]["protocolVersion"] == "2025-06-18"
    assert known["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert known["result"]["serverInfo"]["name"] == "sdetkit"
    assert unknown is not None
    assert unknown["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSIONS[0]


def test_tools_are_listed_with_their_input_schemas() -> None:
    response = mcp_server.Server(cwd=Path.cwd()).handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )

    assert response is not None
    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert set(tools) == {"verify_change", "gate_fast"}
    for tool in tools.values():
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"]


def test_notifications_get_no_answer_and_unknown_methods_an_error() -> None:
    server = mcp_server.Server(cwd=Path.cwd())

    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    unknown = server.handle({"jsonrpc": "2.0", "id": 9, "method": "resources/list"})
    assert unknown is not None and unknown["error"]["code"] == mcp_server.METHOD_NOT_FOUND
    tool = server.handle(
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "rm_rf"}}
    )
    assert tool is not None and tool["error"]["code"] == mcp_server.INVALID_PARAMS


def test_bad_tool_arguments_are_a_tool_error_not_a_crash(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    result = _call(server, "verify_change", {"head": "HEAD", "patch": "x.diff"})

    assert result["isError"] is True
    assert "give one of" in result["content"][0]["text"]
    for bad in ({"pr": 0}, {"pr": "7"}, {"pr": True}, {"pr": 7, "head": "HEAD"}):
        assert _call(server, "verify_change", bad)["isError"] is True


def test_verify_change_takes_a_pull_request_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        return subprocess.CompletedProcess(args, 2, stdout="", stderr="no such pull request")

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    mcp_server.verify_change_tool({"pr": 123, "base": "v1.0"}, cwd=tmp_path, timeout=60)

    [args] = ran
    assert args[2:6] == ["--pr", "123", "--base", "v1.0"]


def test_verify_change_checks_the_agents_uncommitted_work(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _uncommitted_fix(repo)
    status_before = _git(repo, "status", "--porcelain")

    result = _call(mcp_server.Server(cwd=repo, timeout=300), "verify_change", {})

    structured = result["structuredContent"]
    assert result["isError"] is False, result
    assert structured["status"] == "VERIFIED", structured
    # The new, untracked test is part of the change, and it fails without the fix.
    assert structured["proving_tests"] == ["tests.test_add::test_add"]
    assert result["content"][0]["text"].startswith("### :white_check_mark: SDETKit verify change")
    # Nothing in the repository moved: not the working tree, not the index.
    assert _git(repo, "status", "--porcelain") == status_before
    assert _git(repo, "diff", "--cached") == ""


def test_gate_fast_returns_the_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    # The interpreter running these tests stands in for the project's environment; without
    # one, gate fast rightly reads NOT_RUN (the project is not installed anywhere).
    monkeypatch.setenv("VIRTUAL_ENV", sys.prefix)
    # pytest finds the src/ package the way the project configures it.
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "calc"\nversion = "0"\n\n[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        encoding="utf-8",
    )
    (repo / "tests" / "test_zero.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )

    result = _call(
        mcp_server.Server(cwd=tmp_path, timeout=300),
        "gate_fast",
        {"repo_root": "repo", "only": "pytest"},
    )

    assert result["structuredContent"]["verdict"] == "NO_SHIP", result
    assert "pytest" in result["structuredContent"]["failed_steps"]
    assert "NO_SHIP" in result["content"][0]["text"]


def test_the_server_speaks_json_lines_on_stdio(tmp_path: Path) -> None:
    lines = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin = io.StringIO("\n".join(json.dumps(line) for line in lines) + "\nnot json\n")
    stdout = io.StringIO()

    mcp_server.serve(stdin, stdout, cwd=tmp_path, timeout=60)

    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [reply.get("id") for reply in replies] == [1, 2, None]
    assert replies[2]["error"]["code"] == mcp_server.PARSE_ERROR


def test_python_m_sdetkit_mcp_answers_an_agent(tmp_path: Path) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]

    completed = subprocess.run(
        [sys.executable, "-m", "sdetkit", "mcp"],
        input="".join(json.dumps(message) + "\n" for message in messages),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    replies = [json.loads(line) for line in completed.stdout.splitlines()]
    assert [reply["id"] for reply in replies] == [1, 2]
    assert {tool["name"] for tool in replies[1]["result"]["tools"]} == {
        "verify_change",
        "gate_fast",
    }


def test_the_working_tree_patch_includes_untracked_files_and_leaves_the_index(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    _uncommitted_fix(repo)
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("ignored\n", encoding="utf-8")

    patch = change_verifier.working_tree_patch(repo)

    assert "+++ b/tests/test_add.py" in patch
    assert "+++ b/src/calc/__init__.py" in patch
    assert "build/out.txt" not in patch
    assert _git(repo, "diff", "--cached") == ""
    assert "?? tests/test_add.py" in _git(repo, "status", "--porcelain")


def test_verify_change_working_tree_with_nothing_to_verify(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    rc = change_verifier.main(
        ["--working-tree", "--repo-root", str(repo), "--out-dir", str(tmp_path / "o")]
    )

    assert rc == 2


def test_verify_change_pr_one_and_a_base_without_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        return subprocess.CompletedProcess(args, 2, stdout="", stderr="")

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    # Pull request #1 is a pull request.
    mcp_server.verify_change_tool({"pr": 1}, cwd=tmp_path, timeout=60)
    assert ran[0][2:4] == ["--pr", "1"]
    # A base with nothing to compare it with: the uncommitted work has its own base.
    with pytest.raises(mcp_server.ToolError, match="`base` needs"):
        mcp_server.verify_change_tool({"base": "v1.0"}, cwd=tmp_path, timeout=60)
    assert len(ran) == 1
