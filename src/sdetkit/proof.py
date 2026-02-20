from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import cast

_DAY3_PROOF_FLOW = [
    {
        "artifact": "doctor-proof",
        "step": "Doctor proof snapshot",
        "command": "python -m sdetkit doctor --format text",
        "expected": ["doctor score:", "recommendations:"],
        "purpose": "Captures repo health evidence for the Day 3 proof pack.",
    },
    {
        "artifact": "repo-audit-proof",
        "step": "Repo audit proof snapshot",
        "command": "python -m sdetkit repo audit --format text",
        "expected": ["Repo audit:", "Result:"],
        "purpose": "Captures governance/policy output for trust and release reviews.",
    },
    {
        "artifact": "security-proof",
        "step": "Security proof snapshot",
        "command": "python -m sdetkit security report --format text",
        "expected": ["security scan:", "top findings:"],
        "purpose": "Captures security findings evidence for operational handoff.",
    },
]

_DAY3_HINTS = [
    "Capture terminal screenshots immediately after each successful proof command.",
    "Use --strict in CI to enforce that all three Day 3 proof snapshots are valid.",
    "Use --format markdown --output docs/artifacts/day3-proof-sample.md to publish a shareable evidence bundle.",
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit proof")
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--output", default="", help="Optional output file path.")
    p.add_argument(
        "--execute",
        action="store_true",
        help="Run each proof command and attach pass/fail status.",
    )
    p.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-command timeout when --execute is enabled.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any proof command fails.",
    )
    return p


def _run_command(
    command: str | Sequence[str], timeout_seconds: float
) -> tuple[int, str, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(
        shlex.split(command) if isinstance(command, str) else list(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    duration = time.perf_counter() - start
    return proc.returncode, proc.stdout, proc.stderr, duration


def _execute_flow(timeout_seconds: float) -> list[dict[str, object]]:
    execution: list[dict[str, object]] = []
    for item in _DAY3_PROOF_FLOW:
        result: dict[str, object] = {
            "artifact": item["artifact"],
            "step": item["step"],
            "status": "not-run",
            "exit_code": None,
            "duration_seconds": 0.0,
            "missing_snippets": [],
            "error": "",
        }
        try:
            rc, stdout, stderr, duration = _run_command(item["command"], timeout_seconds)
        except subprocess.TimeoutExpired:
            result["status"] = "error"
            result["error"] = f"timeout after {timeout_seconds:.1f}s"
            result["duration_seconds"] = timeout_seconds
            execution.append(result)
            continue

        missing = [snippet for snippet in item["expected"] if snippet not in stdout]
        result["status"] = "pass" if rc == 0 and not missing else "fail"
        result["exit_code"] = rc
        result["duration_seconds"] = round(duration, 3)
        result["missing_snippets"] = missing
        if rc != 0 and stderr.strip():
            result["error"] = stderr.strip().splitlines()[-1]
        execution.append(result)
    return execution


def _as_text(execution: list[dict[str, object]]) -> str:
    lines = ["Day 3 proof pack", ""]
    for item in _DAY3_PROOF_FLOW:
        lines.append(f"[{item['step']}]")
        lines.append(f"  artifact : {item['artifact']}")
        lines.append(f"  command  : {item['command']}")
        lines.append(f"  expected : {item['expected'][0]} | {item['expected'][1]}")
        lines.append(f"  purpose  : {item['purpose']}")
        lines.append("")

    if execution:
        lines.append("Execution results")
        for result in execution:
            lines.append(
                f"- {result['artifact']}: {result['status']} (exit={result['exit_code']}, duration={result['duration_seconds']}s)"
            )
            missing = cast(list[object], result.get("missing_snippets") or [])
            if missing:
                lines.append(f"  missing snippets: {', '.join(str(x) for x in missing)}")
            err = str(result.get("error") or "")
            if err:
                lines.append(f"  error: {err}")
        lines.append("")

    lines.append("Day 3 boost hints")
    for hint in _DAY3_HINTS:
        lines.append(f"- {hint}")
    return "\n".join(lines) + "\n"


def _as_markdown(execution: list[dict[str, object]]) -> str:
    lines = [
        "# Day 3 proof pack",
        "",
        "| Artifact | Step | Command | Expected snippets | Purpose |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in _DAY3_PROOF_FLOW:
        expected = f"`{item['expected'][0]}` + `{item['expected'][1]}`"
        lines.append(
            f"| `{item['artifact']}` | {item['step']} | `{item['command']}` | {expected} | {item['purpose']} |"
        )

    if execution:
        lines.extend(["", "## Execution results", ""])
        lines.extend(
            [
                "| Artifact | Status | Exit code | Duration (s) | Missing snippets | Error |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for result in execution:
            missing = (
                ", ".join(str(x) for x in cast(list[object], result.get("missing_snippets") or []))
                or "-"
            )
            error = str(result.get("error") or "-").replace("|", "\\|")
            lines.append(
                f"| `{result['artifact']}` | {result['status']} | {result['exit_code']} | {result['duration_seconds']} | {missing} | {error} |"
            )

    lines.extend(["", "## Day 3 boost hints", ""])
    for hint in _DAY3_HINTS:
        lines.append(f"- {hint}")
    return "\n".join(lines) + "\n"


def _as_json(execution: list[dict[str, object]]) -> str:
    payload = {
        "name": "day3-proof-pack",
        "steps": _DAY3_PROOF_FLOW,
        "execution": execution,
        "hints": _DAY3_HINTS,
    }
    return json.dumps(payload, indent=2) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    execution = _execute_flow(args.timeout_seconds) if args.execute else []
    if args.format == "markdown":
        rendered = _as_markdown(execution)
    elif args.format == "json":
        rendered = _as_json(execution)
    else:
        rendered = _as_text(execution)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")

    print(rendered, end="")

    if args.strict and any(item.get("status") != "pass" for item in execution):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
