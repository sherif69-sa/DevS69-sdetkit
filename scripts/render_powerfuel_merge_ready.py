#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from powerfuel_common import artifact_path, load_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render merge-ready Powerfuel summary")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--out", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    baseline = load_json(artifact_path("baseline", args.date_tag))
    weekly = load_json(artifact_path("weekly", args.date_tag))
    score = load_json(artifact_path("contract", args.date_tag).with_name(f"powerfuel-consolidation-score-{args.date_tag}.json"))
    contract = load_json(artifact_path("contract", args.date_tag))

    lines = [
        f"# Powerfuel Merge-Ready Summary ({args.date_tag})",
        "",
        f"- Workflow count: {baseline.get('kpis', {}).get('workflow_count')}",
        f"- Duplicate trigger paths: {baseline.get('kpis', {}).get('duplicate_trigger_paths')}",
        f"- Consolidation readiness score: {score.get('score')} ({score.get('priority_lane')})",
        f"- Weekly report status: {weekly.get('status')}",
        f"- Contract check status: {contract.get('status')}",
        "",
        "## Merge Gate",
        "- READY" if contract.get("status") == "pass" else "- NOT READY",
    ]

    out = Path(args.out or f"docs/artifacts/powerfuel-merge-ready-{args.date_tag}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
