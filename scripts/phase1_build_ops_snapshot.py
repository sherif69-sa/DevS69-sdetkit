#!/usr/bin/env python3
"""Build Phase 1 weekly ops snapshot + quality debt register from baseline artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RISK_WEIGHTS = {
    "doctor": 100,
    "enterprise_contracts": 95,
    "primary_docs_map": 80,
    "gate_release": 75,
    "gate_fast": 70,
    "ruff": 50,
    "pytest": 60,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _debt_register(summary: dict[str, Any]) -> list[dict[str, Any]]:
    checks = summary.get("checks", []) if isinstance(summary, dict) else []
    if not isinstance(checks, list):
        checks = []

    rows: list[dict[str, Any]] = []
    for row in checks:
        if not isinstance(row, dict):
            continue
        check_id = str(row.get("id", "")).strip()
        ok = bool(row.get("ok", False))
        if not check_id or ok:
            continue
        score = RISK_WEIGHTS.get(check_id, 40)
        impact = "high" if score >= 80 else "medium" if score >= 60 else "low"
        rows.append(
            {
                "check_id": check_id,
                "risk_score": score,
                "impact": impact,
                "owner_hint": "platform-engineering" if score >= 70 else "repo-maintainers",
                "recommendation": f"Address failing check '{check_id}' and rerun make phase1-baseline",
            }
        )

    rows.sort(key=lambda item: (-int(item["risk_score"]), item["check_id"]))
    return rows


def build_ops_snapshot(summary: dict[str, Any], status: dict[str, Any], next_actions: dict[str, Any]) -> dict[str, Any]:
    debt = _debt_register(summary)
    accomplished = status.get("accomplished", []) if isinstance(status, dict) else []
    not_yet = status.get("not_yet", []) if isinstance(status, dict) else []
    if not isinstance(accomplished, list):
        accomplished = []
    if not isinstance(not_yet, list):
        not_yet = []
    total = len(accomplished) + len(not_yet)
    progress = round((len(accomplished) / total) * 100, 1) if total else 0

    return {
        "schema_version": "sdetkit.phase1_ops_snapshot.v1",
        "generated_at": _utc_now(),
        "phase": "phase1",
        "progress_percent": progress,
        "completed_items": len(accomplished),
        "remaining_items": len(not_yet),
        "hard_blockers": status.get("hard_blockers", []),
        "recommended_next_actions": next_actions.get("next_actions", []),
        "quality_debt_register": debt,
        "top_risk_item": debt[0] if debt else None,
    }


def _to_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Phase 1 weekly ops snapshot",
        "",
        f"- Generated at: {snapshot.get('generated_at', '')}",
        f"- Progress: {snapshot.get('progress_percent', 0)}%",
        f"- Completed items: {snapshot.get('completed_items', 0)}",
        f"- Remaining items: {snapshot.get('remaining_items', 0)}",
        "",
        "## Hard blockers",
    ]

    hard_blockers = snapshot.get("hard_blockers", [])
    if isinstance(hard_blockers, list) and hard_blockers:
        lines.extend(f"- {item}" for item in hard_blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Recommended next actions"])
    actions = snapshot.get("recommended_next_actions", [])
    if isinstance(actions, list) and actions:
        lines.extend(f"- {item}" for item in actions)
    else:
        lines.append("- none")

    lines.extend(["", "## Quality debt register (ranked)"])
    debt = snapshot.get("quality_debt_register", [])
    if isinstance(debt, list) and debt:
        for item in debt:
            lines.append(
                f"- {item.get('check_id')}: risk={item.get('risk_score')} impact={item.get('impact')} "
                f"owner={item.get('owner_hint')}"
            )
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 ops snapshot from baseline artifacts.")
    parser.add_argument("--summary", default="build/phase1-baseline/phase1-baseline-summary.json")
    parser.add_argument("--status", default="build/phase1-baseline/phase1-status.json")
    parser.add_argument("--next-actions", default="build/phase1-baseline/phase1-next-actions.json")
    parser.add_argument("--out-json", default="build/phase1-baseline/phase1-ops-snapshot.json")
    parser.add_argument("--out-md", default="build/phase1-baseline/phase1-ops-snapshot.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    summary = _load_json(Path(args.summary))
    status = _load_json(Path(args.status))
    next_actions = _load_json(Path(args.next_actions))

    snapshot = build_ops_snapshot(summary, status, next_actions)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(snapshot), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        print("phase1-ops-snapshot: OK")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
