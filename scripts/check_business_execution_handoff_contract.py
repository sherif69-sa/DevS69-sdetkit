#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-handoff.v1"


def validate_handoff_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")
    for key in (
        "week1_status",
        "week1_start_date",
        "progress_gate",
        "progress_completion_percent",
        "history_records",
        "latest_gate_counts",
        "next_tasks",
    ):
        if key not in payload:
            errors.append(f"missing {key}")
    gate_counts = payload.get("latest_gate_counts")
    if gate_counts is not None and not isinstance(gate_counts, dict):
        errors.append("latest_gate_counts must be object")
    tasks = payload.get("next_tasks")
    if tasks is not None and not isinstance(tasks, list):
        errors.append("next_tasks must be list")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution handoff artifact contract.")
    parser.add_argument("--artifact", default="build/business-execution/business-execution-handoff.json")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_handoff_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
