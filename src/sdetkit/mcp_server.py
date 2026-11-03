"""`sdetkit mcp`: SDETKit as an MCP server, so a coding agent can check its own work.

It speaks the Model Context Protocol over stdio (one JSON-RPC 2.0 message per line) and offers
two tools:

- ``verify_change`` runs ``sdetkit verify change`` on the agent's change: by default the
  uncommitted work in the repository, untracked files included, against HEAD. It answers
  VERIFIED, REVIEW, FAILED or NOT_RUN, with the findings (tests removed, emptied or skipped) and
  which of the change's tests fail without it; for FAILED, why each broken test fails.
- ``gate_fast`` runs ``sdetkit gate fast``: the repository's lint, format, types and tests, with
  one verdict and the first failure.

Each tool runs SDETKit in a subprocess, so nothing a check prints can reach the protocol stream.
The tools run the repository's own tests and tools, as the agent's own commands would.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TextIO

from sdetkit.versioning import tool_version

JsonObject = dict[str, Any]

# Newest first. The tools use nothing that changed between these revisions.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SERVER_NAME = "sdetkit"
DEFAULT_TIMEOUT_SECONDS = 1800

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602

_REPO_ROOT = {
    "type": "string",
    "description": "Repository to check (default: the server's working directory).",
}
TOOLS: list[JsonObject] = [
    {
        "name": "verify_change",
        "title": "Verify a change",
        "description": (
            "Run the repository's tests before and after a change in a temporary clone and check "
            "that no test was removed, emptied, skipped or configured away. With no `head` or "
            "`patch`, it verifies the uncommitted work (untracked files included) against HEAD: "
            "call it before you commit or open a pull request. Answers VERIFIED, REVIEW, FAILED "
            "or NOT_RUN, the reasons, which of the change's tests fail without it and, for "
            "FAILED, why each broken test fails. "
            "The repository's working tree is not modified."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "base": {
                    "type": "string",
                    "description": "Commit the change starts from (with `head` or `patch`).",
                },
                "head": {"type": "string", "description": "Commit or branch holding the change."},
                "patch": {
                    "type": "string",
                    "description": "Path of a unified diff to verify on top of `base`.",
                },
                "pytest_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments for the test runner, such as test paths.",
                },
                "runner": {
                    "type": "string",
                    "enum": ["auto", "pytest", "vitest", "jest", "node", "go"],
                    "description": "Test runner (default auto: pytest in a Python project, "
                    "otherwise the one package.json uses, otherwise go test with a go.mod).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "gate_fast",
        "title": "Run the fast quality gate",
        "description": (
            "Run the repository's own checks (ruff, mypy, pytest, and other test suites it "
            "configures) and return one verdict (SHIP, REVIEW, NOT_RUN or NO_SHIP), the first "
            "failure and the command to run next."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "only": {
                    "type": "string",
                    "description": "Comma-separated steps to run, for example `ruff,pytest`.",
                },
            },
            "additionalProperties": False,
        },
    },
]


class ToolError(ValueError):
    """Arguments a tool cannot run with."""


def _sdetkit(args: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )


def _repo_root(arguments: Mapping[str, Any], cwd: Path) -> Path:
    root = (cwd / str(arguments.get("repo_root") or ".")).resolve()
    if not root.is_dir():
        raise ToolError(f"repo_root is not a directory: {root}")
    return root


def _strings(arguments: Mapping[str, Any], key: str) -> list[str]:
    value = arguments.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ToolError(f"{key} must be a list of strings")
    return value


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def verify_change_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    head, patch, base = (str(arguments.get(key) or "") for key in ("head", "patch", "base"))
    if head and patch:
        raise ToolError("give `head` or `patch`, not both")
    if base and not (head or patch):
        raise ToolError("`base` needs `head` or `patch`; without them the uncommitted work is used")
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        source = ["--head", head] if head else ["--patch", patch] if patch else ["--working-tree"]
        args = [
            "verify",
            "change",
            *source,
            *(["--base", base] if base else []),
            "--runner",
            str(arguments.get("runner") or "auto"),
            "--repo-root",
            str(root),
            "--out-dir",
            str(out / "report"),
            "--summary-out",
            str(out / "summary.md"),
            "--format",
            "json",
            "--",
            *_strings(arguments, "pytest_args"),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        summary = _read(out / "summary.md").strip()
        try:
            report = json.loads(completed.stdout)
        except ValueError:
            report = {}
    status = str(report.get("status") or "NOT_RUN")
    text = summary or completed.stderr.strip() or f"sdetkit exited with {completed.returncode}"
    return {
        "text": text,
        "structured": {
            "status": status,
            "verdict": (report.get("verdict") or {}).get("decision", "NOT_RUN"),
            "reasons": report.get("reasons", [completed.stderr.strip()] if not report else []),
            "next_action": report.get("next_action", ""),
            "proving_tests": ((report.get("tests") or {}).get("proof") or {}).get("proving", []),
            "findings": [finding.get("code") for finding in report.get("findings", [])],
            "failures": (report.get("tests") or {}).get("failures", {}),
        },
        "error": not report,
    }


def gate_fast_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    only = str(arguments.get("only") or "")
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        args = [
            "gate",
            "fast",
            "--root",
            str(root),
            "--format",
            "json",
            "--out",
            str(out / "gate-fast.json"),
            "--summary-out",
            str(out / "summary.md"),
            *(["--only", only] if only else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        summary = _read(out / "summary.md").strip()
        try:
            payload = json.loads(_read(out / "gate-fast.json") or "{}")
        except ValueError:
            payload = {}
    verdict = payload.get("verdict") or {}
    text = summary or completed.stderr.strip() or f"sdetkit exited with {completed.returncode}"
    return {
        "text": text,
        "structured": {
            "verdict": verdict.get("decision", "NOT_RUN"),
            "reasons": verdict.get("reasons", []),
            "next_action": payload.get("next_action", {}),
            "failed_steps": payload.get("failed_steps", []),
        },
        "error": not payload,
    }


HANDLERS: dict[str, Callable[..., JsonObject]] = {
    "verify_change": verify_change_tool,
    "gate_fast": gate_fast_tool,
}


def _result(request_id: Any, result: JsonObject) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class Server:
    """One MCP session: answers requests, ignores notifications."""

    def __init__(self, *, cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.cwd = cwd
        self.timeout = timeout

    def handle(self, message: Any) -> JsonObject | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        method = message.get("method")
        if "id" not in message:
            return None  # a notification, such as notifications/initialized
        request_id = message["id"]
        params = message.get("params") or {}
        if method == "initialize":
            requested = str(params.get("protocolVersion") or "")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return _result(
                request_id,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": tool_version()},
                    "instructions": (
                        "Call verify_change before you commit or open a pull request: it checks "
                        "that your change passes the repository's tests without weakening them. "
                        "When it answers FAILED, its failures say why each broken test fails."
                    ),
                },
            )
        if method == "ping":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._call(request_id, params)
        return _error(request_id, METHOD_NOT_FOUND, f"unknown method: {method}")

    def _call(self, request_id: Any, params: Mapping[str, Any]) -> JsonObject:
        name = params.get("name")
        handler = HANDLERS.get(str(name))
        if handler is None:
            return _error(request_id, INVALID_PARAMS, f"unknown tool: {name}")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "arguments must be an object")
        try:
            outcome = handler(arguments, cwd=self.cwd, timeout=self.timeout)
        except (ToolError, OSError, subprocess.TimeoutExpired) as exc:
            return _result(
                request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            )
        return _result(
            request_id,
            {
                "content": [{"type": "text", "text": outcome["text"]}],
                "structuredContent": outcome["structured"],
                "isError": bool(outcome["error"]),
            },
        )


def serve(stdin: TextIO, stdout: TextIO, *, cwd: Path, timeout: int) -> None:
    server = Server(cwd=cwd, timeout=timeout)
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response: JsonObject | None = _error(None, PARSE_ERROR, "invalid JSON")
        else:
            response = server.handle(message)
        if response is not None:
            stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="sdetkit mcp",
        description=(
            "Serve SDETKit to coding agents over the Model Context Protocol (stdio): the "
            "verify_change and gate_fast tools. Add it to an agent, for example "
            "`claude mcp add sdetkit -- python -m sdetkit mcp`."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Longest a tool may run",
    )
    args = parser.parse_args(argv)
    serve(sys.stdin, sys.stdout, cwd=Path.cwd(), timeout=args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
