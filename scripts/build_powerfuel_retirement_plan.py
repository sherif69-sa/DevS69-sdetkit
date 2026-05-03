#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from powerfuel_common import artifact_path, dump_json, load_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Powerfuel workflow retirement plan from shadow-mode report")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--shadow-log", default=None)
    p.add_argument("--batch-size", type=int, default=5)
    p.add_argument("--out", default=None)
    p.add_argument("--generated-at", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    shadow_path = Path(args.shadow_log) if args.shadow_log else artifact_path("shadow", args.date_tag)
    payload = load_json(shadow_path)
    candidates = payload.get("retirement_candidates", []) if isinstance(payload.get("retirement_candidates", []), list) else []
    selected = candidates[: max(1, args.batch_size)]

    batch: list[dict[str, Any]] = []
    for row in selected:
        wf = row.get("workflow")
        batch.append(
            {
                "workflow": wf,
                "retirement_priority_score": row.get("retirement_priority_score"),
                "parity_required": True,
                "parity_check_command": f"act -W .github/workflows/{wf} || gh workflow run {wf}",
                "rollback_hint": f"git checkout HEAD~1 -- .github/workflows/{wf}",
                "status": "pending-shadow-parity",
            }
        )

    out_payload = {
        "date": args.date_tag,
        "status": "retirement-plan-created",
        "generated_at": args.generated_at or datetime.now(timezone.utc).isoformat(),
        "inputs": {"shadow_log": str(shadow_path), "batch_size": args.batch_size, "candidate_count": len(candidates)},
        "batch": batch,
        "notes": [
            "Run parity checks and compare gate/coverage artifacts before deleting workflow files.",
            "Only mark status=ready-to-retire after parity evidence exists in weekly report.",
        ],
    }

    out = Path(args.out) if args.out else artifact_path("retirement", args.date_tag)
    dump_json(out, out_payload)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
