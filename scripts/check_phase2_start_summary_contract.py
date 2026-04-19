#!/usr/bin/env python3
"""Validate Phase 2 startup workflow summary contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_KEYS = {
    "schema_version",
    "generated_at",
    "ok",
    "failed_steps",
    "next_actions",
    "steps",
}
EXPECTED_SCHEMA = "sdetkit.phase2_start_workflow.v1"
REQUIRED_STEP_SUBSTRINGS = (
    "sdetkit phase2-kickoff",
    "scripts/check_phase2_kickoff_contract.py",
    "scripts/check_operator_essentials_contract.py",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate phase2-start summary contract.")
    parser.add_argument("--summary", default="build/phase2-start/phase2-start-summary.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    summary_path = Path(args.summary)
    errors: list[str] = []
    payload: dict[str, object] = {}

    if not summary_path.is_file():
        errors.append(f"missing summary file: {summary_path}")
    else:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        missing = sorted(REQUIRED_KEYS.difference(payload.keys()))
        if missing:
            errors.append(f"missing required keys: {missing}")
        if payload.get("schema_version") != EXPECTED_SCHEMA:
            errors.append(
                f"schema_version mismatch: expected {EXPECTED_SCHEMA}, got {payload.get('schema_version')}"
            )
        steps = payload.get("steps", [])
        if not isinstance(steps, list) or not steps:
            errors.append("steps must be a non-empty list")
        else:
            commands = [str(step.get("command", "")) for step in steps if isinstance(step, dict)]
            for expected in REQUIRED_STEP_SUBSTRINGS:
                if not any(expected in cmd for cmd in commands):
                    errors.append(f"missing required step command substring: {expected}")

    result = {
        "ok": not errors,
        "schema_version": "sdetkit.phase2_start_summary_contract.v1",
        "summary": str(summary_path),
        "errors": errors,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("phase2-start-summary-contract: OK" if result["ok"] else "phase2-start-summary-contract: FAIL")
        for item in errors:
            print(f"- {item}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
