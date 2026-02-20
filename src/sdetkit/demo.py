from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

_DEMO_FLOW = [
    {
        "step": "Health check",
        "command": "python -m sdetkit doctor --format text",
        "expected": [
            "doctor score:",
            "recommendations:",
        ],
        "why": "Confirms repository hygiene and points to the highest-leverage fixes first.",
    },
    {
        "step": "Repository audit",
        "command": "python -m sdetkit repo audit --format text",
        "expected": [
            "Repo audit:",
            "Result:",
        ],
        "why": "Surfaces policy, CI, and governance gaps in a report-ready format.",
    },
    {
        "step": "Security baseline",
        "command": "python -m sdetkit security report --format text",
        "expected": [
            "security scan:",
            "top findings:",
        ],
        "why": "Produces a security-focused snapshot that can be attached to release reviews.",
    },
]

_HINTS = [
    "Use --execute when recording a live Day 2 walkthrough so each step is validated.",
    "Use --format markdown --output docs/artifacts/day2-demo-closeout.md to save a shareable run artifact.",
    "If a snippet check fails, rerun a single command manually and compare output with the expected markers.",
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit demo")
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional file path to also write the rendered demo flow.",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Run each demo command and attach pass/fail execution results.",
    )
    p.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Timeout used for each command when --execute is enabled.",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop execution on the first failed or errored step.",
    )
    p.add_argument(
        "--target-seconds",
        type=float,
        default=60.0,
        help="Demo SLA target used to evaluate total execution duration.",
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


def _execute_flow(timeout_seconds: float, fail_fast: bool) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for item in _DEMO_FLOW:
        result: dict[str, object] = {
            "step": item["step"],
            "command": item["command"],
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
            results.append(result)
            if fail_fast:
                break
            continue

        missing = [snippet for snippet in item["expected"] if snippet not in stdout]
        status = "pass" if rc == 0 and not missing else "fail"
        result["status"] = status
        result["exit_code"] = rc
        result["duration_seconds"] = round(duration, 3)
        result["missing_snippets"] = missing
        if status == "fail" and stderr.strip():
            result["error"] = stderr.strip().splitlines()[-1]
        results.append(result)
        if fail_fast and status != "pass":
            break
    return results


def _execution_summary(
    execution_results: list[dict[str, object]], target_seconds: float
) -> dict[str, object]:
    if not execution_results:
        return {}
    total_seconds = 0.0
    for result in execution_results:
        total_seconds += float(cast(Any, result.get("duration_seconds") or 0.0))
    total = round(total_seconds, 3)
    return {
        "total_duration_seconds": total,
        "target_seconds": float(target_seconds),
        "within_target": total <= target_seconds,
    }


def _as_text(execution_results: list[dict[str, object]], target_seconds: float) -> str:
    lines = ["Day 2 demo path (target: ~60 seconds)", ""]
    for item in _DEMO_FLOW:
        lines.append(f"[{item['step']}]")
        lines.append(f"  run     : {item['command']}")
        lines.append(f"  expect  : {item['expected'][0]} | {item['expected'][1]}")
        lines.append(f"  outcome : {item['why']}")
        lines.append("")

    if execution_results:
        summary = _execution_summary(execution_results, target_seconds)
        lines.append("Execution results")
        for result in execution_results:
            lines.append(
                f"- {result['step']}: {result['status']} (exit={result['exit_code']}, duration={result['duration_seconds']}s)"
            )
            missing = cast(list[object], result.get("missing_snippets") or [])
            if missing:
                lines.append(f"  missing snippets: {', '.join(str(x) for x in missing)}")
            err = str(result.get("error") or "")
            if err:
                lines.append(f"  error: {err}")
        lines.append(
            f"- SLA: {summary['total_duration_seconds']}s total vs {summary['target_seconds']}s target -> "
            f"{'PASS' if summary['within_target'] else 'FAIL'}"
        )
        lines.append("")

    lines.append("Closeout hints")
    for hint in _HINTS:
        lines.append(f"- {hint}")
    return "\n".join(lines)


def _as_markdown(execution_results: list[dict[str, object]], target_seconds: float) -> str:
    rows = [
        "# Day 2 demo path (target: ~60 seconds)",
        "",
        "| Step | Command | Expected output snippets | Outcome |",
        "|---|---|---|---|",
    ]
    for item in _DEMO_FLOW:
        expected = "<br>".join(f"`{snippet}`" for snippet in item["expected"])
        rows.append(f"| {item['step']} | `{item['command']}` | {expected} | {item['why']} |")

    if execution_results:
        summary = _execution_summary(execution_results, target_seconds)
        rows.extend(
            [
                "",
                "## Execution results",
                "",
                "| Step | Status | Exit code | Duration (s) | Missing snippets |",
                "|---|---|---:|---:|---|",
            ]
        )
        for result in execution_results:
            missing = cast(list[object], result.get("missing_snippets") or [])
            missing_text = "<br>".join(f"`{snippet}`" for snippet in missing) if missing else "-"
            rows.append(
                f"| {result['step']} | {result['status']} | {result['exit_code']} | {result['duration_seconds']} | {missing_text} |"
            )
        rows.extend(
            [
                "",
                "## SLA summary",
                "",
                f"- Total duration: `{summary['total_duration_seconds']}s`",
                f"- Target: `{summary['target_seconds']}s`",
                f"- Within target: `{'yes' if summary['within_target'] else 'no'}`",
            ]
        )

    rows.extend(["", "## Closeout hints", ""])
    rows.extend(f"- {hint}" for hint in _HINTS)
    rows.append("")
    rows.append(
        "Related docs: [README quick start](../README.md#quick-start), [repo audit](repo-audit.md)."
    )
    return "\n".join(rows)


def _as_json(execution_results: list[dict[str, object]], target_seconds: float) -> str:
    return json.dumps(
        {
            "name": "day2-demo-path",
            "steps": _DEMO_FLOW,
            "execution": execution_results,
            "sla": _execution_summary(execution_results, target_seconds),
            "hints": _HINTS,
        },
        indent=2,
        sort_keys=True,
    )


def _render(fmt: str, execution_results: list[dict[str, object]], target_seconds: float) -> str:
    if fmt == "json":
        return _as_json(execution_results, target_seconds)
    if fmt == "markdown":
        return _as_markdown(execution_results, target_seconds)
    return _as_text(execution_results, target_seconds)


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    execution_results: list[dict[str, object]] = []
    if ns.execute:
        execution_results = _execute_flow(ns.timeout_seconds, ns.fail_fast)

    rendered = _render(ns.format, execution_results, ns.target_seconds)
    print(rendered)

    if ns.output:
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        trailing = "" if rendered.endswith("\n") else "\n"
        out_path.write_text(rendered + trailing, encoding="utf-8")

    if not ns.execute:
        return 0
    return 0 if all(r["status"] == "pass" for r in execution_results) else 1
