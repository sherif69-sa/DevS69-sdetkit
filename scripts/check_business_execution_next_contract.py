#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-next.v1"


def validate_next_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")
    if not isinstance(payload.get("pending_count"), int):
        errors.append("pending_count must be int")
    tasks = payload.get("next_tasks")
    if not isinstance(tasks, list):
        errors.append("next_tasks must be a list")
    else:
        for idx, task in enumerate(tasks):
            if not isinstance(task, str) or not task.strip():
                errors.append(f"next_tasks[{idx}] must be non-empty string")
    command = payload.get("recommended_command")
    if command is not None and not isinstance(command, str):
        errors.append("recommended_command must be null or string")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution next-actions artifact contract.")
    parser.add_argument("--artifact", default="build/business-execution/business-execution-week1-next.json")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_next_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
