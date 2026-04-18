#!/usr/bin/env python3
"""Build a prioritized blocker register for the next Phase 1 pass."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


RISK_PRIORITY = {
    "doctor": 100,
    "enterprise_contracts": 95,
    "primary_docs_map": 90,
    "build": 85,
    "validate": 80,
    "operationalize": 70,
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_blocker_register(next_pass: dict[str, Any], control_loop: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    checks = next_pass.get("blocking_required_checks", [])
    if isinstance(checks, list):
        for check in checks:
            cid = str(check)
            rows.append(
                {
                    "blocker": cid,
                    "category": "required_check",
                    "priority": RISK_PRIORITY.get(cid, 60),
                    "recommended_action": f"Resolve {cid} and rerun make phase1-dashboard",
                }
            )

    stages = next_pass.get("missing_control_loop_stages", [])
    if isinstance(stages, list):
        for stage in stages:
            sid = str(stage)
            rows.append(
                {
                    "blocker": sid,
                    "category": "control_loop_stage",
                    "priority": RISK_PRIORITY.get(sid, 55),
                    "recommended_action": f"Complete {sid} stage before closeout",
                }
            )

    if not rows:
        # fallback: infer from control-loop rows if card had no blockers list
        for row in control_loop.get("stages", []):
            if isinstance(row, dict) and not bool(row.get("ok", False)):
                sid = str(row.get("stage", "unknown"))
                rows.append(
                    {
                        "blocker": sid,
                        "category": "control_loop_stage",
                        "priority": RISK_PRIORITY.get(sid, 50),
                        "recommended_action": str(row.get("action_if_missing", "Run next phase1 action")),
                    }
                )

    rows.sort(key=lambda item: (-int(item["priority"]), item["blocker"]))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 blocker register.")
    parser.add_argument("--next-pass", default="build/phase1-baseline/phase1-next-pass-card.json")
    parser.add_argument("--control-loop", default="build/phase1-baseline/phase1-control-loop-report.json")
    parser.add_argument("--out-json", default="build/phase1-baseline/phase1-blocker-register.json")
    parser.add_argument("--out-csv", default="build/phase1-baseline/phase1-blocker-register.csv")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    next_pass = _load_json(Path(args.next_pass))
    control_loop = _load_json(Path(args.control_loop))

    if not next_pass and not control_loop:
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_blocker_register.v1",
            "reason": "missing next-pass and control-loop artifacts",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase1-blocker-register: FAIL ({payload['reason']})")
        return 1

    rows = build_blocker_register(next_pass, control_loop)
    payload = {
        "ok": True,
        "schema_version": "sdetkit.phase1_blocker_register.v1",
        "count": len(rows),
        "rows": rows,
    }

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["blocker", "category", "priority", "recommended_action"])
        writer.writeheader()
        writer.writerows(rows)

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-blocker-register: OK")
        print(f"- blockers: {len(rows)}")
        print(f"- json: {out_json}")
        print(f"- csv: {out_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
