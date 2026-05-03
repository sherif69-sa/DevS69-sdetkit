#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from powerfuel_common import artifact_path, dump_json, load_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Powerfuel consolidation readiness score")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--baseline", default=None)
    p.add_argument("--shadow", default=None)
    p.add_argument("--out", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    baseline = load_json(Path(args.baseline) if args.baseline else artifact_path("baseline", args.date_tag))
    shadow = load_json(Path(args.shadow) if args.shadow else artifact_path("shadow", args.date_tag))

    workflow_count = int((baseline.get("kpis", {}) or {}).get("workflow_count") or 0)
    dup_paths = int((baseline.get("kpis", {}) or {}).get("duplicate_trigger_paths") or 0)
    candidates = shadow.get("retirement_candidates", []) if isinstance(shadow.get("retirement_candidates", []), list) else []
    top_score = int(candidates[0].get("retirement_priority_score", 0)) if candidates else 0

    score = max(0, min(100, int((dup_paths * 0.5) + (top_score * 0.3) + (workflow_count * 0.2))))
    lane = "high" if score >= 70 else "medium" if score >= 40 else "low"

    payload = {
        "date": args.date_tag,
        "status": "consolidation-score-generated",
        "score": score,
        "priority_lane": lane,
        "inputs": {
            "workflow_count": workflow_count,
            "duplicate_trigger_paths": dup_paths,
            "top_retirement_priority_score": top_score,
            "candidate_count": len(candidates),
        },
        "next_actions": [
            "Focus parity checks on top-ranked retirement candidates.",
            "Track score weekly; trend down as retirements complete.",
        ],
    }

    out = Path(args.out) if args.out else artifact_path("contract", args.date_tag).with_name(f"powerfuel-consolidation-score-{args.date_tag}.json")
    dump_json(out, payload)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
