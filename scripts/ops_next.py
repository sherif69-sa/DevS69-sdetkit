from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("follow-up payload must be JSON object")
    return payload


def _priority_value(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority, 9)


def build_next(payload: dict[str, Any], limit: int) -> dict[str, Any]:
    recs = payload.get("recommendations", [])
    if not isinstance(recs, list):
        recs = []

    cleaned: list[dict[str, str]] = []
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        priority = str(rec.get("priority", "P9"))
        title = str(rec.get("title", ""))
        action = str(rec.get("action", ""))
        cleaned.append({"priority": priority, "title": title, "action": action})

    cleaned.sort(key=lambda item: _priority_value(item["priority"]))
    next_items = cleaned[: max(1, limit)]

    return {
        "decision": payload.get("decision", "NO-SHIP"),
        "next_command": payload.get("next_command", "make ops-daily"),
        "recommendations": next_items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print top next actions from ops follow-up payload"
    )
    parser.add_argument("--followup", type=Path, default=Path("build/ops/followup.json"))
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    payload = _load_json(args.followup)
    result = build_next(payload, args.limit)

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    print(f"OPS_DECISION={result['decision']}")
    print(f"OPS_NEXT_COMMAND={result['next_command']}")
    print("OPS_TOP_ACTIONS=")
    for idx, rec in enumerate(result["recommendations"], start=1):
        print(f"{idx}. [{rec['priority']}] {rec['title']} :: {rec['action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
