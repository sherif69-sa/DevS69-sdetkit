#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-handoff.v1"


def build_handoff(
    week1: dict[str, Any],
    progress: dict[str, Any],
    rollup: dict[str, Any],
    next_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "week1_status": week1.get("status"),
        "week1_start_date": week1.get("start_date"),
        "progress_gate": progress.get("gate_decision", {}).get("status"),
        "progress_completion_percent": progress.get("task_summary", {}).get("completion_percent"),
        "history_records": rollup.get("history_records"),
        "latest_gate_counts": rollup.get("gate_counts"),
        "next_tasks": next_payload.get("next_tasks", []),
        "recommended_command": next_payload.get("recommended_command"),
    }


def render_handoff_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Business Execution Handoff Summary",
        "",
        f"- Week-1 status: {payload.get('week1_status')}",
        f"- Week-1 start date: {payload.get('week1_start_date')}",
        f"- Progress gate: {payload.get('progress_gate')}",
        f"- Completion percent: {payload.get('progress_completion_percent')}",
        f"- History records: {payload.get('history_records')}",
        "",
        "## Gate counts",
    ]
    for gate, count in (payload.get("latest_gate_counts") or {}).items():
        lines.append(f"- {gate}: {count}")
    lines.append("")
    lines.append("## Next tasks")
    tasks = payload.get("next_tasks") or []
    if not tasks:
        lines.append("- No pending tasks.")
    else:
        for task in tasks:
            lines.append(f"- [ ] {task}")
    lines.append("")
    if payload.get("recommended_command"):
        lines.append("## Recommended command")
        lines.append(f"`{payload['recommended_command']}`")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build business execution handoff summary from generated artifacts.")
    parser.add_argument("--week1", default="build/business-execution/business-execution-week1.json")
    parser.add_argument("--progress", default="build/business-execution/business-execution-week1-progress.json")
    parser.add_argument(
        "--rollup",
        default="build/business-execution/business-execution-week1-progress-rollup.json",
    )
    parser.add_argument("--next", dest="next_json", default="build/business-execution/business-execution-week1-next.json")
    parser.add_argument("--out-json", default="build/business-execution/business-execution-handoff.json")
    parser.add_argument("--out-md", default="build/business-execution/business-execution-handoff.md")
    args = parser.parse_args(argv)

    week1 = json.loads(Path(args.week1).read_text(encoding="utf-8"))
    progress = json.loads(Path(args.progress).read_text(encoding="utf-8"))
    rollup = json.loads(Path(args.rollup).read_text(encoding="utf-8"))
    next_payload = json.loads(Path(args.next_json).read_text(encoding="utf-8"))
    payload = build_handoff(week1, progress, rollup, next_payload)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_handoff_md(payload), encoding="utf-8")

    print(f"business-execution-handoff: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
