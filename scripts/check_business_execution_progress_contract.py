#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-progress.v1"
ALLOWED_GATES = {"pass", "conditional-pass", "fail"}


def validate_progress_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")

    summary = payload.get("task_summary")
    if not isinstance(summary, dict):
        errors.append("task_summary must be an object")
    else:
        for key in ("completed", "total", "completion_percent"):
            if key not in summary:
                errors.append(f"missing task_summary.{key}")

    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        errors.append("tasks must be a list")
    else:
        for idx, row in enumerate(tasks):
            if not isinstance(row, dict):
                errors.append(f"tasks[{idx}] must be an object")
                continue
            if not isinstance(row.get("task"), str) or not row.get("task", "").strip():
                errors.append(f"tasks[{idx}].task must be non-empty string")
            if not isinstance(row.get("done"), bool):
                errors.append(f"tasks[{idx}].done must be bool")

    gate = payload.get("gate_decision")
    if not isinstance(gate, dict):
        errors.append("gate_decision must be an object")
    else:
        if gate.get("status") not in ALLOWED_GATES:
            errors.append("gate_decision.status must be pass|conditional-pass|fail")
        reason = gate.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("gate_decision.reason must be non-empty string")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution week-1 progress contract.")
    parser.add_argument(
        "--artifact",
        default="build/business-execution/business-execution-week1-progress.json",
    )
    args = parser.parse_args(argv)

    artifact = Path(args.artifact)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    errors = validate_progress_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": str(artifact)}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
