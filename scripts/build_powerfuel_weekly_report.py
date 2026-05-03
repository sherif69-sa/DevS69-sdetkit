#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from powerfuel_common import artifact_path, dump_json, load_json

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build weekly powerfuel status report from baseline and shadow log")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--baseline", default=None)
    p.add_argument("--shadow-log", default=None)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)
    p.add_argument("--generated-at", default=None)
    p.add_argument("--consolidation-score", default=None)
    return p.parse_args()

def main() -> int:
    args = parse_args()
    baseline = load_json(Path(args.baseline) if args.baseline else artifact_path("baseline", args.date_tag))
    shadow = load_json(Path(args.shadow_log) if args.shadow_log else artifact_path("shadow", args.date_tag))
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat()
    kpis = baseline.get("kpis", {})
    top_candidates = shadow.get("retirement_candidates", [])[:5]
    score_path = Path(args.consolidation_score) if args.consolidation_score else artifact_path("contract", args.date_tag).with_name(f"powerfuel-consolidation-score-{args.date_tag}.json")
    consolidation_score = None
    if score_path.exists():
        consolidation_score = load_json(score_path).get("score")
    report = {"date": args.date_tag, "status": "weekly-report-published", "generated_at": generated_at, "inputs": {"baseline": args.baseline, "shadow_log": args.shadow_log}, "scoreboard": {"workflow_count": kpis.get("workflow_count"), "duplicate_trigger_paths": kpis.get("duplicate_trigger_paths"), "first_proof_success_rate": kpis.get("first_proof_success_rate"), "time_to_first_proof_median_minutes": kpis.get("time_to_first_proof_median_minutes"), "consolidation_readiness_score": consolidation_score}, "next_retirement_batch": top_candidates, "decisions": ["Run shadow-mode parity checks on top 5 retirement candidates before workflow removals.", "Keep CI minute/PR KPI null until telemetry source is connected."]}
    out_json = Path(args.out_json) if args.out_json else artifact_path("weekly", args.date_tag)
    out_md = Path(args.out_md) if args.out_md else artifact_path("weekly", args.date_tag, "md")
    dump_json(out_json, report)
    lines=[f"# Powerfuel Weekly Report ({args.date_tag})","",f"Generated at: {generated_at}","","## KPI Snapshot",f"- Workflow count: {report['scoreboard']['workflow_count']}",f"- Duplicate trigger paths: {report['scoreboard']['duplicate_trigger_paths']}",f"- First-proof success rate: {report['scoreboard']['first_proof_success_rate']}",f"- Time to first proof (median min): {report['scoreboard']['time_to_first_proof_median_minutes']}","","## Next Retirement Batch (Top 5)"]
    for row in top_candidates: lines.append(f"- {row.get('workflow')}: score={row.get('retirement_priority_score')} triggers={','.join(row.get('triggers', []))}")
    lines += ["", "## Decisions"] + [f"- {d}" for d in report["decisions"]]
    out_md.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
