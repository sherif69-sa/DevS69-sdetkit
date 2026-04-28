#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-escalation.v1"
ALLOWED_DECISIONS = {"none", "watch", "escalate"}


def validate_escalation_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")
    for key in (
        "week1_status",
        "progress_gate",
        "completion_percent",
        "pending_count",
        "pending_tasks",
        "decision",
        "reasons",
        "owners_to_ping",
        "recommended_actions",
    ):
        if key not in payload:
            errors.append(f"missing {key}")

    decision = payload.get("decision")
    if decision not in ALLOWED_DECISIONS:
        errors.append("decision must be one of none/watch/escalate")
    if not isinstance(payload.get("pending_count"), int):
        errors.append("pending_count must be int")
    if not isinstance(payload.get("completion_percent"), (int, float)):
        errors.append("completion_percent must be numeric")
    for key in ("pending_tasks", "reasons", "owners_to_ping", "recommended_actions"):
        value = payload.get(key)
        if not isinstance(value, list):
            errors.append(f"{key} must be list")
            continue
        if not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{key} entries must be non-empty strings")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution escalation artifact contract.")
    parser.add_argument("--artifact", default="build/business-execution/business-execution-escalation.json")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_escalation_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
