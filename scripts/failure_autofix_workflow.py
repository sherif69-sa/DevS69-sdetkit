#!/usr/bin/env python3
"""Run a full failure triage + auto-fix suggestion workflow."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path


def _load_plan(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(command: str, timeout_seconds: int) -> tuple[int, str]:
    proc = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    return proc.returncode, proc.stdout


def _suggestions_for(action: dict) -> list[str]:
    category = str(action.get("category", "")).lower()
    security_impact = str(action.get("security_impact", "none")).lower()
    suggestions: list[str] = []

    if "reliability" in category:
        suggestions.extend(
            [
                "Tune timeout thresholds for upstream dependency boundaries.",
                "Implement bounded exponential backoff for transient timeouts.",
                "Add telemetry: timeout rate, retry count, and p95 latency.",
            ]
        )

    if "network" in category:
        suggestions.extend(
            [
                "Enforce idempotency keys for side-effecting operations.",
                "Retry only safe/transient socket reset errors.",
                "Add circuit-breaker guardrail to prevent retry storms.",
            ]
        )

    if security_impact in {"high", "critical", "medium"}:
        suggestions.append("Run security.sh after fix and block merge on new warnings/errors.")

    if not suggestions:
        suggestions.append("Review failing path and add targeted regression test before fix.")

    return suggestions


def _ripgrep_candidates(test_id: str) -> list[str]:
    if "::" not in test_id:
        return []
    test_file = test_id.split("::", 1)[0]
    stem = Path(test_file).stem.replace("test_", "")
    return [f"src/**/{stem}*.py", f"scripts/**/{stem}*.py"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="examples/kits/intelligence/failure-action-plan.json")
    parser.add_argument(
        "--report", default="examples/kits/intelligence/failure-autofix-report.json"
    )
    parser.add_argument("--max-actions", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()

    plan = _load_plan(Path(args.plan))
    actions = plan.get("actions", [])[: args.max_actions]

    results: list[dict] = []
    for action in actions:
        cmd = str(action.get("reproduce_command", "")).strip()
        if not cmd:
            results.append(
                {"issue_id": action.get("issue_id"), "status": "skipped", "reason": "no command"}
            )
            continue

        code, output = _run(cmd, args.timeout_seconds)
        results.append(
            {
                "issue_id": action.get("issue_id"),
                "priority": action.get("priority"),
                "owner": action.get("owner"),
                "status": "failed" if code != 0 else "passed",
                "exit_code": code,
                "reproduce_command": cmd,
                "candidate_code_areas": _ripgrep_candidates(str(action.get("test_id", ""))),
                "auto_fix_suggestions": _suggestions_for(action),
                "output_preview": "\n".join(output.splitlines()[:25]),
            }
        )

    failed = sum(1 for item in results if item.get("status") == "failed")
    passed = sum(1 for item in results if item.get("status") == "passed")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    report = {
        "source_plan": args.plan,
        "executed_actions": len(results),
        "failed_actions": failed,
        "passed_actions": passed,
        "skipped_actions": skipped,
        "results": results,
    }
    out_path = Path(args.report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"{json.dumps(report, indent=2)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
