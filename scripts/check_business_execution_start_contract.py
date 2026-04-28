#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-start.v1"
REQUIRED_OWNER_KEYS = (
    "program_owner",
    "gtm_owner",
    "commercial_owner",
    "solutions_owner",
    "ops_owner",
)


def _is_nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")

    owners = payload.get("owners")
    if not isinstance(owners, dict):
        errors.append("owners must be an object")
        return errors

    for key in REQUIRED_OWNER_KEYS:
        if not _is_nonempty(owners.get(key)):
            errors.append(f"missing owners.{key}")

    status = payload.get("status")
    allowed = {"go", "needs-owner-assignment"}
    if status not in allowed:
        errors.append("status must be one of go or needs-owner-assignment")

    if not _is_nonempty(payload.get("next_action")):
        errors.append("next_action must be a non-empty string")

    if status == "go":
        unresolved = [key for key in REQUIRED_OWNER_KEYS if str(owners.get(key, "")).upper() == "TBD"]
        if unresolved:
            errors.append("status=go is invalid when owners are TBD")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution week-1 artifact contract.")
    parser.add_argument(
        "--artifact",
        default="build/business-execution/business-execution-week1.json",
    )
    parser.add_argument(
        "--require-go",
        action="store_true",
        help="Fail validation unless artifact status is go.",
    )
    args = parser.parse_args(argv)
    artifact = Path(args.artifact)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    errors = validate_contract(payload)
    if args.require_go and payload.get("status") != "go":
        errors.append("status must be go when --require-go is set")
    result = {"ok": not errors, "errors": errors, "artifact": str(artifact)}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
