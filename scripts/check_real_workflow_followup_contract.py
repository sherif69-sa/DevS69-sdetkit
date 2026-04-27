from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object")
    return payload


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_followup(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("schema_version") != "sdetkit.real-workflow-followup.v1":
        errors.append("schema_version must be sdetkit.real-workflow-followup.v1")

    decision = payload.get("decision")
    if decision not in {"SHIP", "NO-SHIP"}:
        errors.append("decision must be SHIP or NO-SHIP")

    threshold_breach = payload.get("threshold_breach")
    if not isinstance(threshold_breach, bool):
        errors.append("threshold_breach must be boolean")

    next_command = payload.get("next_command")
    if next_command not in {"make ops-daily", "make ops-premerge"}:
        errors.append("next_command must be make ops-daily or make ops-premerge")

    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list):
        errors.append("recommendations must be an array")
        return errors

    for idx, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            errors.append(f"recommendations[{idx}] must be an object")
            continue
        for key in ("priority", "title", "action"):
            if key not in rec:
                errors.append(f"recommendations[{idx}] missing {key}")
        priority = rec.get("priority")
        if priority not in {"P0", "P1", "P2", "P3"}:
            errors.append(f"recommendations[{idx}].priority must be P0/P1/P2/P3")
        if not _is_nonempty_string(rec.get("title")):
            errors.append(f"recommendations[{idx}].title must be non-empty string")
        if not _is_nonempty_string(rec.get("action")):
            errors.append(f"recommendations[{idx}].action must be non-empty string")

    return errors


def check_history_rollup(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "sdetkit.real-workflow-followup-history-rollup.v1":
        errors.append(
            "history rollup schema_version must be sdetkit.real-workflow-followup-history-rollup.v1"
        )

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        errors.append("history rollup summary must be object")
        return errors

    for key in (
        "total_runs",
        "ship_runs",
        "no_ship_runs",
        "threshold_breach_runs",
    ):
        if not isinstance(summary.get(key), int):
            errors.append(f"history rollup summary.{key} must be integer")

    ship_rate = summary.get("ship_rate")
    if not isinstance(ship_rate, (int, float)):
        errors.append("history rollup summary.ship_rate must be number")

    top_recs = summary.get("top_recurring_recommendations")
    if not isinstance(top_recs, list):
        errors.append("history rollup summary.top_recurring_recommendations must be array")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ops follow-up contract outputs")
    parser.add_argument("--followup", type=Path, default=Path("build/ops/followup.json"))
    parser.add_argument(
        "--history-rollup", type=Path, default=Path("build/ops/followup-history-rollup.json")
    )
    parser.add_argument("--out", type=Path, default=Path("build/ops/followup-contract-check.json"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    followup = _load_json(args.followup)
    history_rollup = _load_json(args.history_rollup)

    errors = check_followup(followup) + check_history_rollup(history_rollup)
    result = {
        "ok": not errors,
        "errors": errors,
        "followup": str(args.followup),
        "history_rollup": str(args.history_rollup),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"ops follow-up contract: {'OK' if result['ok'] else 'FAIL'}")
        if errors:
            for err in errors:
                print(f" - {err}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
