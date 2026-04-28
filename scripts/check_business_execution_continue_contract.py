#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-continue.v1"


def validate_continue_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")
    for key in ("checkpoint_status", "keep_moving", "selected_command", "reason", "should_run_now"):
        if key not in payload:
            errors.append(f"missing {key}")
    if payload.get("checkpoint_status") not in {"on-track", "due"}:
        errors.append("checkpoint_status must be on-track or due")
    if not isinstance(payload.get("keep_moving"), bool):
        errors.append("keep_moving must be bool")
    if not isinstance(payload.get("should_run_now"), bool):
        errors.append("should_run_now must be bool")
    for key in ("selected_command", "reason"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be non-empty string")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution continue artifact contract.")
    parser.add_argument("--artifact", default="build/business-execution/business-execution-continue.json")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_continue_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
