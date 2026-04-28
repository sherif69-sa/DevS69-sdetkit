#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-horizon.v1"


def build_horizon_payload(
    week1: dict[str, Any],
    progress: dict[str, Any],
    followup: dict[str, Any],
) -> dict[str, Any]:
    completed = int(progress.get("task_summary", {}).get("completed", 0))
    completion_percent = float(progress.get("task_summary", {}).get("completion_percent", 0.0))
    focus_mode = "execution-acceleration" if completed >= 3 else "foundation-build"

    week_2_plan = {
        "day_6_7": [
            "Close remaining week-1 execution tasks.",
            "Baseline KPI dashboard with first live numbers.",
        ],
        "day_8_10": [
            "Run two design-partner discovery sessions.",
            "Capture blockers and update operating memo.",
        ],
        "day_11_14": [
            "Finalize pilot charter and commercial guardrails.",
            "Publish week-2 review with go-forward priorities.",
        ],
    }
    day_90_plan = {
        "day_30": [
            "Pilot execution stable with weekly KPI reviews.",
            "Validated ICP shortlist with conversion evidence.",
        ],
        "day_60": [
            "Two to three active pilots with measured time-to-value.",
            "Commercial packaging v1 validated by pilot outcomes.",
        ],
        "day_90": [
            "Pilot-to-paid conversion path established.",
            "Quarter roadmap and hiring/ops priorities locked.",
        ],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "week1_status": week1.get("status"),
        "progress_gate": progress.get("gate_decision", {}).get("status"),
        "completion_percent": completion_percent,
        "followup_checkpoint_status": followup.get("checkpoint_status"),
        "focus_mode": focus_mode,
        "week_2_plan": week_2_plan,
        "day_90_plan": day_90_plan,
    }


def render_horizon_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Business Execution Horizon Plan (Week-2 + Day-90)",
        "",
        f"- Week-1 status: {payload.get('week1_status')}",
        f"- Progress gate: {payload.get('progress_gate')}",
        f"- Completion percent: {payload.get('completion_percent')}",
        f"- Follow-up checkpoint: {payload.get('followup_checkpoint_status')}",
        f"- Focus mode: {payload.get('focus_mode')}",
        "",
        "## Week-2 plan",
    ]
    for bucket, items in (payload.get("week_2_plan") or {}).items():
        lines.append(f"### {bucket}")
        for item in items:
            lines.append(f"- [ ] {item}")
        lines.append("")
    lines.append("## Day-90 plan")
    for bucket, items in (payload.get("day_90_plan") or {}).items():
        lines.append(f"### {bucket}")
        for item in items:
            lines.append(f"- [ ] {item}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate week-2 and day-90 execution horizon plan.")
    parser.add_argument("--week1", default="build/business-execution/business-execution-week1.json")
    parser.add_argument("--progress", default="build/business-execution/business-execution-week1-progress.json")
    parser.add_argument("--followup", default="build/business-execution/business-execution-followup.json")
    parser.add_argument("--out-json", default="build/business-execution/business-execution-horizon.json")
    parser.add_argument("--out-md", default="build/business-execution/business-execution-horizon.md")
    args = parser.parse_args(argv)

    week1 = json.loads(Path(args.week1).read_text(encoding="utf-8"))
    progress = json.loads(Path(args.progress).read_text(encoding="utf-8"))
    followup = json.loads(Path(args.followup).read_text(encoding="utf-8"))
    payload = build_horizon_payload(week1, progress, followup)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_horizon_md(payload), encoding="utf-8")

    print(f"business-execution-horizon: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
