#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from powerfuel_common import artifact_path, dump_json, load_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build powerfuel shadow-mode workflow consolidation log")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--baseline", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--generated-at", default=None, help="ISO timestamp override for deterministic outputs")
    return p.parse_args()


def retirement_priority_score(triggers: list[str], trigger_counts: Counter[str]) -> int:
    return sum(max(0, trigger_counts.get(t, 0) - 1) for t in triggers)


def main() -> int:
    args = parse_args()
    baseline_path = Path(args.baseline) if args.baseline else artifact_path("baseline", args.date_tag)
    baseline = load_json(baseline_path)
    workflow_trigger_map = baseline.get("workflow_trigger_map", {}) if isinstance(baseline.get("workflow_trigger_map", {}), dict) else {}
    trigger_counts = Counter(baseline.get("trigger_counts", {}))

    candidates: list[dict[str, Any]] = []
    for wf_name, triggers in workflow_trigger_map.items():
        if isinstance(triggers, list):
            candidates.append({"workflow": wf_name, "triggers": sorted(str(t) for t in triggers), "trigger_count": len(triggers), "retirement_priority_score": retirement_priority_score(triggers, trigger_counts)})
    candidates.sort(key=lambda row: (-int(row["retirement_priority_score"]), -int(row["trigger_count"]), str(row["workflow"])))

    payload = {
        "date": args.date_tag,
        "status": "shadow-log-started",
        "generated_at": args.generated_at or datetime.now(timezone.utc).isoformat(),
        "inputs": {"baseline": str(baseline_path), "workflow_count": len(workflow_trigger_map)},
        "summary": {"candidate_count": len(candidates), "top_duplicate_triggers": trigger_counts.most_common(5)},
        "retirement_candidates": candidates,
        "notes": [
            "Priority score is overlap-weighted by duplicated trigger frequency from the baseline artifact.",
            "Use top-ranked candidates for shadow-mode parity and retirement batch planning.",
        ],
    }

    out = Path(args.out) if args.out else artifact_path("shadow", args.date_tag)
    dump_json(out, payload)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
