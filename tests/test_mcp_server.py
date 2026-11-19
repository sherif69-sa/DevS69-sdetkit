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
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "core.autocrlf=false",
            *args,
        ],
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
    assert set(tools) == {
        "verify_change",
        "gate_fast",
        "doctor",
        "diagnose_failure",
        "run_mutation",
        "auto_fix",
        "hunt_flakes",
        "select_impacted_tests",
        "manage_test_quarantine",
        "evaluate_blast_radius",
        "heal_workspace",
        "inject_chaos",
        "shard_test_suite",
        "query_reliability_trends",
        "classify_flake_risk",
        "run_polyglot_tests",
    }
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
        "doctor",
        "diagnose_failure",
        "run_mutation",
        "auto_fix",
        "hunt_flakes",
        "select_impacted_tests",
        "manage_test_quarantine",
        "evaluate_blast_radius",
        "heal_workspace",
        "inject_chaos",
        "shard_test_suite",
        "query_reliability_trends",
        "classify_flake_risk",
        "run_polyglot_tests",
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


def test_doctor_tool_validates_boolean_flags(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in ("yes", 1, [True]):
        result = _call(server, "doctor", {"release": bad})
        assert result["isError"] is True
        assert "release must be true or false" in result["content"][0]["text"]


def test_doctor_tool_passes_selected_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        return subprocess.CompletedProcess(
            args, 0, stdout='{"ok": true, "score": 100, "checks": {}}', stderr=""
        )

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    result = mcp_server.doctor_tool(
        {"release": True, "ci": True, "deps": True, "ascii": True},
        cwd=tmp_path,
        timeout=60,
    )

    [args] = ran
    assert args[:2] == ["doctor", "--format"]
    assert "--release" in args
    assert "--ci" in args
    assert "--deps" in args
    assert "--ascii" in args
    assert result["error"] is False
    assert result["structured"]["ok"] is True
    assert result["structured"]["score"] == 100


def test_diagnose_failure_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    for bad in ({}, {"log_text": "a", "log_path": "b"}):
        result = _call(server, "diagnose_failure", bad)
        assert result["isError"] is True
        assert "give exactly one of" in result["content"][0]["text"]

    for bad_types in ({"log_text": 123}, {"log_path": ["a"]}):
        result = _call(server, "diagnose_failure", bad_types)
        assert result["isError"] is True
        assert "must be a string" in result["content"][0]["text"]

    missing_path = _call(server, "diagnose_failure", {"log_path": "nonexistent.log"})
    assert missing_path["isError"] is True
    assert "log_path does not exist" in missing_path["content"][0]["text"]


def test_diagnose_failure_runs_with_log_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        payload = {
            "ok": True,
            "classification": "PYTEST_ASSERTION_FAILURE",
            "summary": "Targeted test behavior failed",
            "confidence": "high",
            "proof_commands": ["pytest tests/test_calc.py"],
            "next_actions": ["Reproduce the first failing test"],
            "safe_to_auto_fix": False,
        }
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    result = mcp_server.diagnose_failure_tool(
        {"log_text": "FAILED tests/test_calc.py - assert 1 == 2"},
        cwd=tmp_path,
        timeout=60,
    )

    [args] = ran
    assert args[:2] == ["investigate", "failure"]
    assert args[2] == "--log"
    assert args[4:] == ["--format", "json"]
    assert result["error"] is False
    assert result["structured"]["classification"] == "PYTEST_ASSERTION_FAILURE"
    assert "### SDETKit failure diagnosis: PYTEST_ASSERTION_FAILURE" in result["text"]
    assert "`pytest tests/test_calc.py`" in result["text"]
    assert "- Reproduce the first failing test" in result["text"]


def test_diagnose_failure_runs_with_log_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_file = tmp_path / "ci_failure.log"
    log_file.write_text("traceback: zero division", encoding="utf-8")

    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        payload = {
            "ok": True,
            "classification": "ZERO_DIVISION_ERROR",
            "summary": "Division by zero",
            "confidence": "high",
        }
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    server = mcp_server.Server(cwd=tmp_path)
    result = _call(server, "diagnose_failure", {"log_path": "ci_failure.log"})

    assert result["isError"] is False
    assert ran[0][3] == str(log_file.resolve())
    assert result["structuredContent"]["classification"] == "ZERO_DIVISION_ERROR"


def test_run_mutation_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    for bad in (
        {"path": 123},
        {"max_mutants": 0},
        {"max_mutants": 300},
        {"max_mutation_seconds": -5},
    ):
        result = _call(server, "run_mutation", bad)
        assert result["isError"] is True


def test_run_mutation_passes_arguments_to_sdetkit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        payload = {
            "ok": True,
            "ran": True,
            "score": 100.0,
            "killed": 5,
            "survived": 0,
            "total": 5,
            "mutants": [],
            "survivors": [],
        }
        out_idx = args.index("--out")
        Path(args[out_idx + 1]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    server = mcp_server.Server(cwd=tmp_path)
    result = _call(
        server,
        "run_mutation",
        {
            "path": "src/calc.py",
            "pytest_args": ["tests/test_calc.py"],
            "max_mutants": 15,
            "min_mutation_score": 80,
            "max_mutation_seconds": 60,
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["score"] == 100.0
    args = ran[0]
    assert args[:2] == ["verify", "mutation"]
    assert "--path" in args and args[args.index("--path") + 1] == "src/calc.py"
    assert "--max-mutants" in args and args[args.index("--max-mutants") + 1] == "15"
    assert "--min-mutation-score" in args and args[args.index("--min-mutation-score") + 1] == "80.0"
    assert (
        "--max-mutation-seconds" in args and args[args.index("--max-mutation-seconds") + 1] == "60"
    )
    assert "tests/test_calc.py" in args


def test_auto_fix_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    for bad in (
        {"repo_root": "nonexistent_dir_12345"},
        {"apply": "not_a_bool"},
        {"log_text": 123},
        {"log_path": 123},
        {"log_path": "nonexistent_file_12345.log"},
        {"rules": 123},
        {"rules": [123]},
        {"diff": "not_a_bool"},
    ):
        result = _call(server, "auto_fix", bad)
        assert result["isError"] is True


def test_auto_fix_passes_arguments_to_sdetkit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[list[str]] = []

    def sdetkit(args: list[str], *, cwd: Path, timeout: int) -> Any:
        ran.append(args)
        payload = {
            "ok": True,
            "target": "working_tree",
            "applied": True,
            "plan": {
                "eligible": True,
                "confidence": "high",
                "recommended_operation": "RUFF_FORMAT",
                "commands": [["python", "-m", "ruff", "format", "."]],
            },
            "execution": {"executed": True, "returncode": 0},
            "verification": {"verified": True, "passed": True},
        }
        out_idx = args.index("--out")
        Path(args[out_idx + 1]).write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(mcp_server, "_sdetkit", sdetkit)

    server = mcp_server.Server(cwd=tmp_path)
    result = _call(
        server,
        "auto_fix",
        {
            "apply": True,
            "log_text": "ruff format failed",
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["applied"] is True
    args = ran[0]
    assert args[0] == "auto-fix"
    assert "--apply" in args
    assert "--log" in args

    # Test with rules and diff
    result2 = _call(
        server,
        "auto_fix",
        {
            "apply": False,
            "rules": ["format", "whitespace"],
            "diff": True,
        },
    )
    assert result2["isError"] is False
    args2 = ran[1]
    assert args2[0] == "auto-fix"
    assert "--dry-run" in args2
    assert "--rules" in args2
    assert "format,whitespace" in args2
    assert "--diff" in args2


def test_hunt_flakes_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    for bad in (
        {"repo_root": "nonexistent_dir_12345"},
        {"runs": 1},
        {"runs": 101},
        {"runs": "not_an_int"},
        {"max_seconds": "not_a_number"},
    ):
        result = _call(server, "hunt_flakes", bad)
        assert result["isError"] is True


def test_hunt_flakes_calls_flake_hunter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def mock_hunt_flakes(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append({"args": args, "kwargs": kwargs})
        return {
            "schema_version": "sdetkit.flake_hunter.v1",
            "verdict": "deterministic",
            "ok": True,
            "target": kwargs.get("target"),
            "runs_requested": kwargs.get("runs", 5),
            "runs_completed": kwargs.get("runs", 5),
            "passed_count": kwargs.get("runs", 5),
            "failed_count": 0,
            "flaky_tests": [],
            "failing_tests": [],
            "duration_stats": {"mean_ms": 100, "stddev_ms": 5, "min_ms": 95, "max_ms": 105},
            "iterations": [],
        }

    import sdetkit.flake_hunter

    monkeypatch.setattr(sdetkit.flake_hunter, "hunt_flakes", mock_hunt_flakes)

    server = mcp_server.Server(cwd=tmp_path)
    result = _call(
        server,
        "hunt_flakes",
        {
            "target": "tests/test_something.py",
            "runs": 7,
            "shuffle": True,
            "max_seconds": 30.0,
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["verdict"] == "deterministic"
    assert len(calls) == 1
    assert calls[0]["kwargs"]["target"] == "tests/test_something.py"
    assert calls[0]["kwargs"]["runs"] == 7
    assert calls[0]["kwargs"]["shuffle"] is True
    assert calls[0]["kwargs"]["max_seconds"] == 30.0


def test_select_impacted_tests_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    for bad in (
        {"repo_root": "nonexistent_dir_12345"},
        {"files": "not_a_list"},
        {"files": [123]},
        {"base": 123},
        {"run": "not_a_bool"},
    ):
        result = _call(server, "select_impacted_tests", bad)
        assert result["isError"] is True


def test_select_impacted_tests_calls_test_impact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    def mock_analyze(root: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"root": root, "kwargs": kwargs})
        return {
            "schema_version": "sdetkit.test_impact.v1",
            "clean": False,
            "changed_files": ["src/pkg/mod.py"],
            "directly_impacted_tests": ["tests/test_mod.py"],
            "transitively_impacted_tests": [],
            "all_impacted_tests": ["tests/test_mod.py"],
            "total_tests_count": 10,
            "selected_tests_count": 1,
            "reduction_pct": 90.0,
            "recommended_pytest_command": "python -m pytest tests/test_mod.py",
            "confidence": "high",
            "reason": "Selected 1 impacted tests.",
        }

    import sdetkit.dependency_map

    monkeypatch.setattr(sdetkit.dependency_map, "analyze_impact", mock_analyze)

    server = mcp_server.Server(cwd=tmp_path)
    result = _call(
        server,
        "select_impacted_tests",
        {
            "files": ["src/pkg/mod.py"],
            "base": "main",
            "run": False,
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["selected_tests_count"] == 1
    assert len(calls) == 1
    assert calls[0]["kwargs"]["files"] == ["src/pkg/mod.py"]
    assert calls[0]["kwargs"]["base"] == "main"


def test_manage_test_quarantine_validation(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)

    for bad in (
        {},  # missing action
        {"action": "invalid_action"},
        {"action": "add"},  # missing test_id
        {"action": "graduate"},  # missing test_id
        {"action": "list", "manifest_path": 123},  # bad manifest_path type
    ):
        result = _call(server, "manage_test_quarantine", bad)
        assert result["isError"] is True


def test_manage_test_quarantine_tool_flow(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    manifest = tmp_path / "quarantine.json"
    m_path = str(manifest)

    # 1. Add
    res = _call(
        server,
        "manage_test_quarantine",
        {
            "action": "add",
            "test_id": "tests/test_mcp.py::test_case",
            "reason": "intermittent failure",
            "owner": "@devs69",
            "manifest_path": m_path,
        },
    )
    assert res["isError"] is False
    assert res["structuredContent"]["test_id"] == "tests/test_mcp.py::test_case"
    assert "Quarantined Test Added" in res["content"][0]["text"]

    # 2. List
    list_res = _call(
        server,
        "manage_test_quarantine",
        {
            "action": "list",
            "manifest_path": m_path,
        },
    )
    assert list_res["isError"] is False
    assert list_res["structuredContent"]["total_count"] == 1

    # 3. Filter
    filt_res = _call(
        server,
        "manage_test_quarantine",
        {
            "action": "filter",
            "manifest_path": m_path,
        },
    )
    assert filt_res["isError"] is False
    assert "-k" in filt_res["content"][0]["text"]
    assert "not test_case" in filt_res["content"][0]["text"]

    # 4. Audit
    audit_res = _call(
        server,
        "manage_test_quarantine",
        {
            "action": "audit",
            "manifest_path": m_path,
        },
    )
    assert audit_res["isError"] is False
    assert "health_score" in audit_res["structuredContent"]


def test_evaluate_blast_radius_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"files": "not-a-list"},
        {"files": [123]},
        {"base": 456},
    ):
        result = _call(server, "evaluate_blast_radius", bad)
        assert result["isError"] is True


def test_evaluate_blast_radius_tool_flow(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(server, "evaluate_blast_radius", {"files": []})
    assert res["isError"] is False
    assert res["structuredContent"]["clean"] is True
    assert res["structuredContent"]["risk_tier"] == "LOW"
    assert "RISK: CLEAN (0.0%)" in res["content"][0]["text"]


def test_heal_workspace_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"target_test": 123},
        {"log_text": 456},
    ):
        result = _call(server, "heal_workspace", bad)
        assert result["isError"] is True


def test_heal_workspace_tool_flow(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(server, "heal_workspace", {"apply": False})
    assert res["isError"] is False
    assert res["structuredContent"]["schema_version"] == "sdetkit.heal.v1"
    assert "SDETKit Autonomous Self-Healing" in res["content"][0]["text"]


def test_inject_chaos_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"target": 123},
        {"profile": "invalid_profile"},
        {"latency_ms": -10},
        {"fault_rate": 1.5},
        {"runs": 0},
    ):
        result = _call(server, "inject_chaos", bad)
        assert result["isError"] is True


def test_inject_chaos_tool_flow(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    (tests / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(
        server, "inject_chaos", {"runs": 1, "profile": "latency", "latency_ms": 0, "jitter_ms": 0}
    )
    assert res["isError"] is False
    assert res["structuredContent"]["schema_version"] == "sdetkit.chaos.v1"
    assert "SDETKit Chaos Resilience & Injection Engine" in res["content"][0]["text"]


def test_shard_test_suite_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"nodes": 0},
        {"nodes": -2},
        {"nodes": "four"},
        {"index": -1},
        {"index": "zero"},
        {"test_files": "not_a_list"},
        {"test_files": [123]},
    ):
        result = _call(server, "shard_test_suite", bad)
        assert result["isError"] is True


def test_shard_test_suite_tool_flow(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    (tests / "test_a.py").write_text(
        "def test_one(): pass\ndef test_two(): pass\n", encoding="utf-8"
    )
    (tests / "test_b.py").write_text("def test_three(): pass\n", encoding="utf-8")
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(
        server,
        "shard_test_suite",
        {"nodes": 2, "index": 0},
    )
    assert res["isError"] is False
    assert res["structuredContent"]["schema_version"] == "sdetkit.shard.v1"
    assert res["structuredContent"]["nodes"] == 2
    assert "selected_shard" in res["structuredContent"]
    assert "SDETKit Duration-Weighted Test Sharding" in res["content"][0]["text"]


def test_query_reliability_trends_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"days": 0},
        {"days": -10},
        {"days": "thirty"},
        {"metric": "unknown_metric"},
    ):
        result = _call(server, "query_reliability_trends", bad)
        assert result["isError"] is True


def test_query_reliability_trends_tool_flow(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(
        server,
        "query_reliability_trends",
        {"days": 14, "metric": "all"},
    )
    assert res["isError"] is False
    assert res["structuredContent"]["schema_version"] == "sdetkit.trend.v1"
    assert "reliability_velocity_index" in res["structuredContent"]
    assert "SDETKit Release Reliability & Drift Trend Radar" in res["content"][0]["text"]


def test_classify_flake_risk_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"target": 123},
        {"max_risk": -1},
        {"max_risk": 150},
        {"max_risk": "high"},
    ):
        result = _call(server, "classify_flake_risk", bad)
        assert result["isError"] is True


def test_classify_flake_risk_tool_flow(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    (tests / "test_clean.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(
        server,
        "classify_flake_risk",
        {"target": "tests/test_clean.py", "max_risk": 50},
    )
    assert res["isError"] is False
    assert res["structuredContent"]["schema_version"] == "sdetkit.flake_genome.v1"
    assert res["structuredContent"]["risk_tier"] == "PRISTINE"
    assert "SDETKit Flake Genome & Test Anti-Pattern Analysis" in res["content"][0]["text"]


def test_run_polyglot_tests_tool_validates_arguments(tmp_path: Path) -> None:
    server = mcp_server.Server(cwd=tmp_path)
    for bad in (
        {"target": 123},
        {"languages": 456},
        {"languages": [1, 2]},
    ):
        result = _call(server, "run_polyglot_tests", bad)
        assert result["isError"] is True


def test_run_polyglot_tests_tool_flow(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    (tests / "test_simple.py").write_text("def test_pass(): assert True\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='toy'\n", encoding="utf-8")
    server = mcp_server.Server(cwd=tmp_path)
    res = _call(
        server,
        "run_polyglot_tests",
        {"target": ".", "languages": ["python"]},
    )
    assert res["isError"] is False
    assert res["structuredContent"]["schema_version"] == "sdetkit.polyglot_matrix.v1"
    assert "SDETKit Polyglot Test Matrix Radar" in res["content"][0]["text"]
