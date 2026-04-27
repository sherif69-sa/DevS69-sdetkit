from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _priority_value(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(priority, 9)


def check_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("schema_version", "fit", "decision", "next_command", "recommendations")
    for key in required:
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    if payload.get("schema_version") != "sdetkit.adoption_followup.v1":
        errors.append("schema_version must be sdetkit.adoption_followup.v1")

    if payload.get("fit") not in {"unknown", "low", "medium", "high"}:
        errors.append("fit must be one of: unknown, low, medium, high")

    next_command = payload.get("next_command")
    if not isinstance(next_command, str) or not next_command.strip():
        errors.append("next_command must be a non-empty string")

    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations:
        errors.append("recommendations must be a non-empty list")
        return errors

    last_priority = -1
    for idx, rec in enumerate(recommendations, start=1):
        if not isinstance(rec, dict):
            errors.append(f"recommendations[{idx}] must be an object")
            continue
        priority = rec.get("priority")
        title = rec.get("title")
        action = rec.get("action")
        if priority not in {"P0", "P1", "P2"}:
            errors.append(f"recommendations[{idx}].priority must be P0/P1/P2")
            current = 9
        else:
            current = _priority_value(priority)
        if not isinstance(title, str) or not title.strip():
            errors.append(f"recommendations[{idx}].title must be non-empty string")
        if not isinstance(action, str) or not action.strip():
            errors.append(f"recommendations[{idx}].action must be non-empty string")
        if current < last_priority:
            errors.append("recommendations must be sorted by priority (P0 -> P1 -> P2)")
        last_priority = max(last_priority, current)

    top_action = recommendations[0].get("action") if recommendations else None
    if isinstance(top_action, str) and isinstance(next_command, str) and top_action != next_command:
        errors.append("next_command must equal recommendations[0].action")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate adoption-followup contract.")
    parser.add_argument("--followup", type=Path, default=Path("build/adoption-followup.json"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        payload = _load(args.followup)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "errors": [str(exc)], "followup": str(args.followup)}
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("adoption-followup contract: fail")
            print(f"- {exc}")
        return 1

    errors = check_contract(payload)
    result = {"ok": not errors, "errors": errors, "followup": str(args.followup)}
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print("adoption-followup contract: ok")
    else:
        print("adoption-followup contract: fail")
        for row in errors:
            print(f"- {row}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
