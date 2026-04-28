#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "sdetkit.business-execution-inputs.v1"


def validate_inputs_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("schema_version mismatch")

    for key in ("challenge_prompt", "guidelines_zip"):
        value = payload.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            errors.append(f"{key} must be object or null")
            continue
        for required in ("path", "size_bytes", "sha256"):
            if required not in value:
                errors.append(f"missing {key}.{required}")

    prompt = payload.get("challenge_prompt")
    if isinstance(prompt, dict):
        if "line_count" not in prompt:
            errors.append("missing challenge_prompt.line_count")
        if "first_heading" not in prompt:
            errors.append("missing challenge_prompt.first_heading")

    bundle = payload.get("guidelines_zip")
    if isinstance(bundle, dict):
        entry_count = bundle.get("entry_count")
        if not isinstance(entry_count, int):
            errors.append("guidelines_zip.entry_count must be int")
        elif entry_count > 25:
            errors.append("guidelines_zip.entry_count exceeds max25")
        if "entries_preview" not in bundle:
            errors.append("missing guidelines_zip.entries_preview")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate business execution input manifest contract.")
    parser.add_argument("--artifact", default="build/business-execution/business-execution-inputs.json")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    errors = validate_inputs_contract(payload)
    result = {"ok": not errors, "errors": errors, "artifact": args.artifact}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
