#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-followup.v1"
ALLOWED_DECISIONS = {"none", "watch", "escalate"}


def validate_followup_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")
    for key in (
        "progress_gate",
        "escalation_decision",
        "window_hours",
        "pending_count",
        "next_tasks",
        "immediate_actions",
        "recommended_command",
        "keep_moving",
        "history_records",
        "decision_counts",
        "latest_recorded_at",
        "next_checkpoint_at",
        "checkpoint_status",
        "checkpoint_due_in_hours",
        "checkpoint_command",
    ):
        if key not in payload:
            errors.append(f"missing {key}")
    if payload.get("escalation_decision") not in ALLOWED_DECISIONS:
        errors.append("escalation_decision must be one of none/watch/escalate")
    if not isinstance(payload.get("window_hours"), int):
        errors.append("window_hours must be int")
    if not isinstance(payload.get("pending_count"), int):
        errors.append("pending_count must be int")
    for key in ("next_tasks", "immediate_actions"):
        value = payload.get(key)
        if not isinstance(value, list):
            errors.append(f"{key} must be list")
            continue
        if not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{key} entries must be non-empty strings")
    cmd = payload.get("recommended_command")
    if not isinstance(cmd, str) or not cmd.strip():
        errors.append("recommended_command must be non-empty string")
    if not isinstance(payload.get("keep_moving"), bool):
        errors.append("keep_moving must be bool")
    if not isinstance(payload.get("history_records"), int):
        errors.append("history_records must be int")
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        errors.append("decision_counts must be object")
    else:
        for key in ("none", "watch", "escalate"):
            if not isinstance(decision_counts.get(key), int):
                errors.append(f"decision_counts.{key} must be int")
    latest_recorded_at = payload.get("latest_recorded_at")
    if latest_recorded_at is not None and not isinstance(latest_recorded_at, str):
        errors.append("latest_recorded_at must be string or null")
    next_checkpoint_at = payload.get("next_checkpoint_at")
    if next_checkpoint_at is not None and not isinstance(next_checkpoint_at, str):
        errors.append("next_checkpoint_at must be string or null")
    if payload.get("checkpoint_status") not in {"on-track", "due"}:
        errors.append("checkpoint_status must be on-track or due")
    if not isinstance(payload.get("checkpoint_due_in_hours"), (int, float)):
        errors.append("checkpoint_due_in_hours must be numeric")
    checkpoint_command = payload.get("checkpoint_command")
    if not isinstance(checkpoint_command, str) or not checkpoint_command.strip():
        errors.append("checkpoint_command must be non-empty string")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate business execution follow-up artifact contract."
    )
    parser.add_argument(
        "--artifact", default="build/business-execution/business-execution-followup.json"
    )
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_followup_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
