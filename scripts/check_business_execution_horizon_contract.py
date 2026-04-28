#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-horizon.v1"
FOCUS_MODES = {"foundation-build", "execution-acceleration"}


def _validate_plan_section(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    section = payload.get(key)
    if not isinstance(section, dict):
        errors.append(f"{key} must be object")
        return
    if not section:
        errors.append(f"{key} cannot be empty")
        return
    for bucket, items in section.items():
        if not isinstance(bucket, str) or not bucket.strip():
            errors.append(f"{key} bucket names must be non-empty strings")
            continue
        if not isinstance(items, list) or not items:
            errors.append(f"{key}.{bucket} must be non-empty list")
            continue
        if not all(isinstance(item, str) and item.strip() for item in items):
            errors.append(f"{key}.{bucket} entries must be non-empty strings")


def validate_horizon_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")
    for key in (
        "week1_status",
        "progress_gate",
        "completion_percent",
        "followup_checkpoint_status",
        "focus_mode",
        "week_2_plan",
        "day_90_plan",
    ):
        if key not in payload:
            errors.append(f"missing {key}")
    if not isinstance(payload.get("completion_percent"), (int, float)):
        errors.append("completion_percent must be numeric")
    if payload.get("focus_mode") not in FOCUS_MODES:
        errors.append("focus_mode must be foundation-build or execution-acceleration")
    _validate_plan_section(payload, "week_2_plan", errors)
    _validate_plan_section(payload, "day_90_plan", errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution horizon artifact contract.")
    parser.add_argument("--artifact", default="build/business-execution/business-execution-horizon.json")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_horizon_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
