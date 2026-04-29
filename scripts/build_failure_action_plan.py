#!/usr/bin/env python3
"""Generate a prioritized remediation plan from failure intelligence JSON."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SECURITY_WEIGHT = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}


def _load_failures(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("failures payload must be a JSON object")
    return payload


def _sort_key(item: dict) -> tuple[int, int, str]:
    priority = str(item.get("priority", "P3")).upper()
    security = str(item.get("security_impact", "none")).lower()
    return (
        PRIORITY_RANK.get(priority, 99),
        SECURITY_WEIGHT.get(security, 99),
        str(item.get("id", "")),
    )


def _owner_for_category(category: str) -> str:
    mapping = {
        "reliability": "sre-team",
        "network-stability": "platform-network",
        "security": "appsec",
    }
    return mapping.get(category, "qa-lead")


def _build_actions(failures: Iterable[dict]) -> list[dict]:
    actions: list[dict] = []
    for rank, failure in enumerate(sorted(failures, key=_sort_key), start=1):
        category = str(failure.get("category", "unknown"))
        actions.append(
            {
                "rank": rank,
                "issue_id": failure.get("id", "UNKNOWN"),
                "priority": failure.get("priority", "P3"),
                "owner": _owner_for_category(category),
                "status": "planned",
                "category": category,
                "test_id": failure.get("test_id", ""),
                "security_impact": failure.get("security_impact", "none"),
                "next_step": failure.get("fix_recommendation", "Define remediation."),
                "reproduce_command": f"pytest -q {failure.get('test_id', '')}",
                "verify_command": f"pytest -q {failure.get('test_id', '')} --maxfail=1",
                "definition_of_done": "Failing test passes consistently for 3 consecutive runs.",
            }
        )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="examples/kits/intelligence/failures.json")
    parser.add_argument("--output", default="examples/kits/intelligence/failure-action-plan.json")
    args = parser.parse_args()

    payload = _load_failures(Path(args.input))
    failures = payload.get("failures", [])
    if not isinstance(failures, list):
        raise ValueError("`failures` must be a list")

    actions = _build_actions(failures)
    output = {
        "source": args.input,
        "total_actions": len(actions),
        "actions": actions,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"{json.dumps(output, indent=2)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
