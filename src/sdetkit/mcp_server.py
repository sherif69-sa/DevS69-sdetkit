"""`sdetkit mcp`: SDETKit as an MCP server, so a coding agent can check its own work.

It speaks the Model Context Protocol over stdio (one JSON-RPC 2.0 message per line) and offers
seven tools:

- ``verify_change`` runs ``sdetkit verify change`` on the agent's change: by default the
  uncommitted work in the repository, untracked files included, against HEAD. It answers
  VERIFIED, REVIEW, FAILED or NOT_RUN, with the findings (tests removed, emptied or skipped) and
  which of the change's tests fail without it; for FAILED, why each broken test fails.
- ``gate_fast`` runs ``sdetkit gate fast``: the repository's lint, format, types and tests, with
  one verdict and the first failure.
- ``doctor`` runs ``sdetkit doctor``: repository health, environment, dependencies, configuration,
  and release readiness checks with prescriptive remediation actions.
- ``diagnose_failure`` runs ``sdetkit investigate failure``: analyzes error outputs, tracebacks,
  or test logs using adaptive diagnosis, returning root-cause classification and reproduction commands.
- ``run_mutation`` runs ``sdetkit verify mutation``: synthesizes mutants on source code to detect
  gaps in test assertions, returning mutation score, surviving mutants, and prescriptive test hints.
- ``auto_fix`` runs ``sdetkit auto-fix``: plans and optionally executes verified safe mechanical fixes
  (formatting drift, ruff fixable lint) with automated proof verification.
- ``hunt_flakes`` runs ``sdetkit verify flake``: stress-tests target tests over multiple iterations
  to detect non-determinism, measure execution duration variance, and isolate timing races.
- ``select_impacted_tests`` runs ``sdetkit verify impact``: selects and optionally executes the
  minimal subset of directly and transitively impacted tests using AST dependency graph traversal.

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
            "FAILED, why each broken test fails, and which changed lines of code no test runs. "
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
                "pr": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "A GitHub pull request to verify, by number: its head from "
                    "origin, from where it left the default branch (or from `base`).",
                },
                "patch": {
                    "type": "string",
                    "description": "Path of a unified diff to verify on top of `base`.",
                },
                "pytest_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments for the test runner, such as test paths.",
                },
                "project": {
                    "type": "string",
                    "description": "Folder of the repository whose tests run, in a repository "
                    "of several projects (web/ with its package.json, svc/ with its go.mod). "
                    "Default: every project the change touches, in one report.",
                },
                "runner": {
                    "type": "string",
                    "enum": ["auto", "pytest", "vitest", "jest", "node", "go", "maven", "gradle"],
                    "description": "Test runner (default auto: pytest in a Python project, "
                    "otherwise the one package.json uses, otherwise go test with a go.mod, otherwise Maven or Gradle).",
                },
                "network": {
                    "type": "string",
                    "enum": ["allow", "deny"],
                    "description": "deny runs the tests with no network but their own loopback "
                    "(Linux network namespace); use it for code you do not trust yet.",
                },
                "min_changed_coverage": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Percentage of the changed lines of code the tests must run "
                    "(pytest, go test, jest, vitest, node --test, Maven, Gradle); below it the status "
                    "is REVIEW. "
                    "Default 0: only reported.",
                },
                "mutate": {
                    "type": "boolean",
                    "description": "Also alter the changed lines the tests run, one operator or "
                    "constant at a time, and run the tests on each: a mutant every test passes "
                    "with is a changed line no test checks. Each mutant runs the tests again.",
                },
                "max_mutation_seconds": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Start no further mutant after this many seconds (default: "
                    "no limit); the result says how many did not run.",
                },
                "max_mutants": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "At most this many mutants (default 20).",
                },
                "min_mutation_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Percentage of the mutants the tests must catch; below it "
                    "the status is REVIEW. Setting it turns `mutate` on. Default 0: only reported.",
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
    {
        "name": "doctor",
        "title": "Run repository health and readiness checks",
        "description": (
            "Run SDETKit repository doctor checks: inspect environment, dependencies, "
            "configuration, security files, and repo readiness. Returns a health score, "
            "judgment summary, failed checks, recommendations, and prescriptive next actions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "release": {
                    "type": "boolean",
                    "description": "Run release-specific metadata and clean-tree validation.",
                },
                "repo": {
                    "type": "boolean",
                    "description": "Validate gate scripts, templates, and pre-commit hooks.",
                },
                "ci": {
                    "type": "boolean",
                    "description": "Verify CI workflows and security governance files.",
                },
                "deps": {
                    "type": "boolean",
                    "description": "Validate dependency consistency.",
                },
                "ascii": {
                    "type": "boolean",
                    "description": "Verify pure ASCII source files under src/ and tools/.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "diagnose_failure",
        "title": "Diagnose failure logs with adaptive test intelligence",
        "description": (
            "Analyze test failure outputs, tracebacks, or CI logs using SDETKit's adaptive "
            "diagnosis cortex. Returns classified failure signals, root-cause summary, "
            "proof reproduction commands, and a prioritized remediation plan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "log_text": {
                    "type": "string",
                    "description": "Raw test failure text or traceback to diagnose.",
                },
                "log_path": {
                    "type": "string",
                    "description": "Path to a text log file to diagnose (alternative to `log_text`).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_mutation",
        "title": "Run mutation testing on source code to find gaps in test assertions",
        "description": (
            "Synthesize mutants (altering comparison, arithmetic, logic, boolean, negation, "
            "and return operators) on target files or working tree changes, run tests against "
            "each mutant, and report mutation score, surviving mutants, and prescriptive test hints."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "path": {
                    "type": "string",
                    "description": (
                        "Path to a file or folder to mutate. If omitted, mutates working tree change."
                    ),
                },
                "pytest_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments for pytest, such as specific test file paths.",
                },
                "max_mutants": {
                    "type": "integer",
                    "description": "Maximum number of mutants to synthesize and test (1-200, default 20).",
                },
                "min_mutation_score": {
                    "type": "integer",
                    "description": "Required mutation score percentage (0-100, default 0).",
                },
                "max_mutation_seconds": {
                    "type": "number",
                    "description": "Maximum runtime budget in seconds for mutation testing.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "auto_fix",
        "title": "Automatically remediate safe mechanical issues (format drift, fixable lint)",
        "description": (
            "Diagnose failure logs or the working tree for safe mechanical issues "
            "(PRE_COMMIT_FORMAT_DRIFT, RUFF_FIXABLE_LINT), plan safe remediation, "
            "and optionally apply fixes with proof verification."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": {
                    "type": "string",
                    "description": "Root directory of the repository (default: current workspace).",
                },
                "log_text": {
                    "type": "string",
                    "description": "Raw error log or traceback text to diagnose and fix.",
                },
                "log_path": {
                    "type": "string",
                    "description": "Relative path to a saved failure log file.",
                },
                "apply": {
                    "type": "boolean",
                    "description": "Whether to apply the verified safe fix (default: false / dry-run preview).",
                },
                "rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific remediation rules to apply: 'all', 'format', 'imports', "
                        "'unused_imports', 'whitespace', 'lint'."
                    ),
                },
                "diff": {
                    "type": "boolean",
                    "description": "Whether to include unified diff of changes in output (default: false).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "hunt_flakes",
        "title": "Hunt flaky tests, prove test non-determinism, and measure duration variance",
        "description": (
            "Stress-test target tests over multiple randomized iterations to mathematically "
            "detect and prove test non-determinism (flake rate), timing races, and state pollution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "target": {
                    "type": "string",
                    "description": "Target test file or test ID (e.g. tests/test_api.py::test_case).",
                },
                "runs": {
                    "type": "integer",
                    "description": "Number of test iterations to execute (2-100, default 5).",
                },
                "shuffle": {
                    "type": "boolean",
                    "description": "Whether to randomize hash seeds and execution order (default: true).",
                },
                "max_seconds": {
                    "type": "number",
                    "description": "Maximum total runtime budget in seconds for flake hunting.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "select_impacted_tests",
        "title": "Predict and select impacted tests via AST dependency graph traversal",
        "description": (
            "Analyze code changes or working tree diffs using AST dependency graph "
            "traversal to select the minimal set of directly and transitively impacted "
            "tests, skipping unimpacted tests to drastically accelerate verification."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific changed file paths to analyze (default: detects uncommitted git changes).",
                },
                "base": {
                    "type": "string",
                    "description": "Git base reference to diff against (e.g. main, HEAD~1).",
                },
                "run": {
                    "type": "boolean",
                    "description": "Whether to execute the selected impacted tests immediately (default: false).",
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


def _percent(value: Any, name: str = "min_changed_coverage") -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ToolError(f"{name} must be a number from 0 to 100")
    return float(value)


def _mutation_args(arguments: Mapping[str, Any]) -> list[str]:
    mutate = arguments.get("mutate")
    if mutate is not None and not isinstance(mutate, bool):
        raise ToolError("mutate must be true or false")
    limit = arguments.get("max_mutants")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200
    ):
        raise ToolError("max_mutants must be a whole number from 1 to 200")
    score = _percent(arguments.get("min_mutation_score"), "min_mutation_score")
    seconds = arguments.get("max_mutation_seconds")
    if seconds is not None and (
        isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0
    ):
        raise ToolError("max_mutation_seconds must be a number above 0")
    return [
        *(["--mutate"] if mutate else []),
        *(["--max-mutants", str(limit)] if limit is not None else []),
        *(["--max-mutation-seconds", str(seconds)] if seconds is not None else []),
        *(["--min-mutation-score", str(score)] if score else []),
    ]


def _mutation(mutation: Mapping[str, Any] | None) -> JsonObject | None:
    """The mutants an agent acts on: the score, and the changed lines no test checks."""

    if not mutation:
        return None
    return {
        "ran": bool(mutation.get("ran")),
        "score": mutation.get("score"),
        "survived": [
            {key: item.get(key, "") for key in ("path", "line", "before", "after", "hint")}
            for item in mutation.get("mutants", [])
            if item["outcome"] == "survived"
        ],
        "reason": mutation.get("reason", ""),
    }


def _changed_lines(coverage: Mapping[str, Any]) -> JsonObject:
    """The changed-line coverage an agent acts on: the share, and the lines no test runs."""

    return {
        "measured": bool(coverage.get("measured")),
        "percent": coverage.get("percent"),
        "not_run": {
            item["path"]: item["not_run"] for item in coverage.get("files", []) if item["not_run"]
        },
        "reason": coverage.get("reason", ""),
    }


def verify_change_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    head, patch, base = (str(arguments.get(key) or "") for key in ("head", "patch", "base"))
    pr = arguments.get("pr")
    if pr is not None and (isinstance(pr, bool) or not isinstance(pr, int) or pr < 1):
        raise ToolError("pr must be a pull request number")
    if sum(bool(value) for value in (head, patch, pr)) > 1:
        raise ToolError("give one of `head`, `patch` or `pr`")
    if base and not (head or patch or pr):
        raise ToolError(
            "`base` needs `head`, `patch` or `pr`; without them the uncommitted work is used"
        )
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        source = (
            ["--head", head]
            if head
            else ["--patch", patch]
            if patch
            else ["--pr", str(pr)]
            if pr
            else ["--working-tree"]
        )
        args = [
            "verify",
            "change",
            *source,
            *(["--base", base] if base else []),
            "--runner",
            str(arguments.get("runner") or "auto"),
            *(["--project", str(arguments["project"])] if arguments.get("project") else []),
            "--network",
            str(arguments.get("network") or "allow"),
            "--min-changed-coverage",
            str(_percent(arguments.get("min_changed_coverage"))),
            *_mutation_args(arguments),
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
            "projects": [
                {key: item.get(key) for key in ("project", "runner", "status", "reasons")}
                for item in report.get("projects") or []
            ],
            "proving_tests": ((report.get("tests") or {}).get("proof") or {}).get("proving", []),
            "findings": [finding.get("code") for finding in report.get("findings", [])],
            "failures": (report.get("tests") or {}).get("failures", {}),
            "changed_lines": _changed_lines(report.get("changed_coverage") or {}),
            "mutation": _mutation(report.get("mutation")),
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


def doctor_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    for flag in ("release", "repo", "ci", "deps", "ascii"):
        val = arguments.get(flag)
        if val is not None and not isinstance(val, bool):
            raise ToolError(f"{flag} must be true or false")
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "doctor.json"
        args = [
            "doctor",
            "--format",
            "json",
            "--out",
            str(json_out),
            *(["--release"] if arguments.get("release") else []),
            *(["--repo"] if arguments.get("repo") else []),
            *(["--ci"] if arguments.get("ci") else []),
            *(["--deps"] if arguments.get("deps") else []),
            *(["--ascii"] if arguments.get("ascii") else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
    ok = bool(payload.get("ok"))
    score = payload.get("score")
    judgment = payload.get("judgment") or {}
    next_action = payload.get("next_action") or {}
    failed_checks = (payload.get("quality") or {}).get("failed_check_ids", [])
    status_label = "PASS" if ok else "FAIL"
    text = (
        f"### SDETKit doctor: {status_label} (score: {score}%)\n\n"
        f"**Judgment**: {judgment.get('summary', 'No summary')}\n"
        f"**Next move**: {(judgment.get('top_judgment') or {}).get('next_move', 'No immediate action required.')}\n"
    )
    if failed_checks:
        text += f"\n**Failed checks**: {', '.join(failed_checks)}\n"
    if next_action.get("next_command"):
        text += f"**Next command**: `{next_action['next_command']}`\n"
    if completed.stderr.strip():
        text += f"\n```\n{completed.stderr.strip()}\n```"
    return {
        "text": text.strip(),
        "structured": {
            "ok": ok,
            "score": score,
            "failed_checks": failed_checks,
            "judgment": {
                "status": judgment.get("status", ""),
                "severity": judgment.get("severity", ""),
                "summary": judgment.get("summary", ""),
                "next_move": (judgment.get("top_judgment") or {}).get("next_move", ""),
            },
            "recommendations": payload.get("recommendations", []),
            "next_action": next_action,
        },
        "error": not ok,
    }


def diagnose_failure_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    log_text = arguments.get("log_text")
    log_path = arguments.get("log_path")
    if bool(log_text) == bool(log_path):
        raise ToolError("give exactly one of `log_text` or `log_path`")
    if log_text is not None and not isinstance(log_text, str):
        raise ToolError("log_text must be a string")
    if log_path is not None and not isinstance(log_path, str):
        raise ToolError("log_path must be a string")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        if log_text is not None:
            target_log = out / "failure.log"
            target_log.write_text(log_text, encoding="utf-8")
        else:
            target_log = (root / str(log_path)).resolve()
            if not target_log.is_file():
                raise ToolError(f"log_path does not exist: {target_log}")

        args = [
            "investigate",
            "failure",
            "--log",
            str(target_log),
            "--format",
            "json",
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(completed.stdout or "{}")
        except ValueError:
            payload = {}

    ok = bool(payload.get("ok", True)) and bool(payload)
    classification = payload.get("classification") or "UNKNOWN_FAILURE"
    summary = payload.get("summary") or "Failure analysis unavailable"
    confidence = payload.get("confidence") or "medium"
    proof_commands = payload.get("proof_commands") or []
    next_actions = payload.get("next_actions") or []
    safe_to_auto_fix = bool(payload.get("safe_to_auto_fix"))

    text = (
        f"### SDETKit failure diagnosis: {classification}\n\n"
        f"**Summary**: {summary}\n"
        f"**Confidence**: {confidence} | **Safe to auto-fix**: {safe_to_auto_fix}\n"
    )
    if proof_commands:
        cmds = "\n".join(f"- `{cmd}`" for cmd in proof_commands)
        text += f"\n**Proof commands**:\n{cmds}\n"
    if next_actions:
        actions = "\n".join(f"- {action}" for action in next_actions)
        text += f"\n**Next actions**:\n{actions}\n"
    if completed.stderr.strip():
        text += f"\n```\n{completed.stderr.strip()}\n```"

    return {
        "text": text.strip(),
        "structured": payload,
        "error": not ok,
    }


def run_mutation_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target_path = arguments.get("path")
    if target_path is not None and not isinstance(target_path, str):
        raise ToolError("path must be a string")
    limit = arguments.get("max_mutants")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200
    ):
        raise ToolError("max_mutants must be a whole number from 1 to 200")
    score = _percent(arguments.get("min_mutation_score"), "min_mutation_score")
    seconds = arguments.get("max_mutation_seconds")
    if seconds is not None and (
        isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0
    ):
        raise ToolError("max_mutation_seconds must be a number above 0")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "mutation.json"
        args = [
            "verify",
            "mutation",
            "--repo-root",
            str(root),
            "--format",
            "json",
            "--out",
            str(json_out),
            *(["--path", str(target_path)] if target_path else []),
            *(["--max-mutants", str(limit)] if limit is not None else []),
            *(["--min-mutation-score", str(score)] if score else []),
            *(["--max-mutation-seconds", str(seconds)] if seconds is not None else []),
            "--",
            *_strings(arguments, "pytest_args"),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}

    ok = bool(payload.get("ok", True)) and bool(payload)
    from sdetkit.mutation_cli import render_markdown

    text = render_markdown(payload) if payload else completed.stderr.strip()
    return {
        "text": text.strip() or f"sdetkit exited with {completed.returncode}",
        "structured": payload,
        "error": not ok,
    }


def auto_fix_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    log_text = arguments.get("log_text")
    log_path = arguments.get("log_path")
    apply_val = arguments.get("apply")
    if apply_val is not None and not isinstance(apply_val, bool):
        raise ToolError("apply must be a boolean")
    apply_fix = bool(apply_val)

    rules_val = arguments.get("rules")
    if rules_val is not None:
        if isinstance(rules_val, list):
            if not all(isinstance(r, str) for r in rules_val):
                raise ToolError("rules must be an array of strings")
            rules_str = ",".join(rules_val)
        elif isinstance(rules_val, str):
            rules_str = rules_val
        else:
            raise ToolError("rules must be an array of strings or comma-separated string")
    else:
        rules_str = None

    diff_val = arguments.get("diff")
    if diff_val is not None and not isinstance(diff_val, bool):
        raise ToolError("diff must be a boolean")
    include_diff = bool(diff_val)

    if log_text is not None and not isinstance(log_text, str):
        raise ToolError("log_text must be a string")
    if log_path is not None and not isinstance(log_path, str):
        raise ToolError("log_path must be a string")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "auto-fix.json"
        args = [
            "auto-fix",
            "--repo-root",
            str(root),
            "--format",
            "json",
            "--out",
            str(json_out),
            *(["--apply"] if apply_fix else ["--dry-run"]),
        ]
        if rules_str:
            args.extend(["--rules", rules_str])
        if include_diff:
            args.append("--diff")
        if log_text is not None:
            target_log = out / "failure.log"
            target_log.write_text(log_text, encoding="utf-8")
            args.extend(["--log", str(target_log)])
        elif log_path is not None:
            target_log = (root / str(log_path)).resolve()
            if not target_log.is_file():
                raise ToolError(f"log_path does not exist: {target_log}")
            args.extend(["--log", str(target_log)])

        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}

    ok = bool(payload.get("ok", True)) and bool(payload)
    from sdetkit.auto_fix import render_markdown as render_auto_fix_markdown

    text = (
        render_auto_fix_markdown(payload, dry_run=not apply_fix)
        if payload
        else completed.stderr.strip()
    )
    return {
        "text": text.strip() or f"sdetkit exited with {completed.returncode}",
        "structured": payload,
        "error": not ok,
    }


def hunt_flakes_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target = arguments.get("target")
    runs = arguments.get("runs")
    if runs is not None:
        if not isinstance(runs, int) or runs < 2 or runs > 100:
            raise ToolError("runs must be an integer between 2 and 100")
    else:
        runs = 5
    shuffle = bool(arguments.get("shuffle", True))
    max_seconds = arguments.get("max_seconds")
    if max_seconds is not None and not isinstance(max_seconds, (int, float)):
        raise ToolError("max_seconds must be a number above 0")

    from sdetkit.flake_hunter import hunt_flakes, render_markdown

    payload = hunt_flakes(
        root=root,
        target=str(target) if target else None,
        runs=runs,
        shuffle=shuffle,
        timeout=timeout,
        max_seconds=float(max_seconds) if max_seconds is not None else None,
    )
    md = render_markdown(payload)
    return {
        "text": md,
        "structured": payload,
        "error": not payload.get("ok", True),
    }


def select_impacted_tests_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    files_val = arguments.get("files")
    if files_val is not None:
        if not isinstance(files_val, list) or not all(isinstance(f, str) for f in files_val):
            raise ToolError("files must be an array of strings")
        files = files_val
    else:
        files = None

    base_val = arguments.get("base")
    if base_val is not None and not isinstance(base_val, str):
        raise ToolError("base must be a string")
    base = base_val

    run_val = arguments.get("run")
    if run_val is not None and not isinstance(run_val, bool):
        raise ToolError("run must be a boolean")
    should_run = bool(run_val)

    from sdetkit.test_impact import analyze_impact, render_markdown, run_impacted_tests

    report = analyze_impact(root, files=files, base=base)
    exec_res = None
    if should_run and report.get("all_impacted_tests"):
        exec_res = run_impacted_tests(report, root=root, timeout=timeout)

    md = render_markdown(report, exec_res)
    payload = {**report, "execution": exec_res} if exec_res else report
    error = bool(exec_res and not exec_res.get("ok"))
    return {
        "text": md,
        "structured": payload,
        "error": error,
    }


HANDLERS: dict[str, Callable[..., JsonObject]] = {
    "verify_change": verify_change_tool,
    "gate_fast": gate_fast_tool,
    "doctor": doctor_tool,
    "diagnose_failure": diagnose_failure_tool,
    "run_mutation": run_mutation_tool,
    "auto_fix": auto_fix_tool,
    "hunt_flakes": hunt_flakes_tool,
    "select_impacted_tests": select_impacted_tests_tool,
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
                        "Call gate_fast to run the fast quality gate, doctor to check repository "
                        "health and readiness, diagnose_failure to analyze failure logs, "
                        "run_mutation to check assertion thoroughness, auto_fix to "
                        "remediate safe mechanical issues, hunt_flakes to prove test determinism, "
                        "and select_impacted_tests to accelerate test execution via AST test impact analysis. "
                        "When a tool answers FAILED, its output says why each check failed."
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
            "verify_change, gate_fast, doctor, diagnose_failure, run_mutation, auto_fix, "
            "hunt_flakes, and select_impacted_tests tools. Add it to an agent, for example `claude mcp add sdetkit -- python -m sdetkit mcp`."
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
