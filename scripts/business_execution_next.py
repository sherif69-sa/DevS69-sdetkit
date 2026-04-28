#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-next.v1"


def build_next_payload(progress_payload: dict[str, Any], limit: int) -> dict[str, Any]:
    tasks = progress_payload.get("tasks", [])
    pending = [row["task"] for row in tasks if isinstance(row, dict) and not row.get("done", False)]
    selected = pending[: max(0, limit)]
    command = None
    if selected:
        command = "python scripts/business_execution_progress.py " + " ".join(
            f'--done "{task}"' for task in selected
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": progress_payload.get("schema_version"),
        "gate_status": progress_payload.get("gate_decision", {}).get("status"),
        "pending_count": len(pending),
        "next_tasks": selected,
        "recommended_command": command,
    }


def render_next_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Business Execution Next Actions",
        "",
        f"- Gate status: {payload.get('gate_status')}",
        f"- Pending tasks: {payload.get('pending_count')}",
        "",
        "## Suggested next tasks",
    ]
    tasks = payload.get("next_tasks", [])
    if not tasks:
        lines.append("- No pending tasks.")
    else:
        for task in tasks:
            lines.append(f"- [ ] {task}")
    lines.append("")
    if payload.get("recommended_command"):
        lines.append("## Suggested command")
        lines.append(f"`{payload['recommended_command']}`")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate concrete next actions from week-1 progress artifact."
    )
    parser.add_argument(
        "--progress",
        default="build/business-execution/business-execution-week1-progress.json",
    )
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--out-json",
        default="build/business-execution/business-execution-week1-next.json",
    )
    parser.add_argument(
        "--out-md",
        default="build/business-execution/business-execution-week1-next.md",
    )
    args = parser.parse_args(argv)

    progress_payload = json.loads(Path(args.progress).read_text(encoding="utf-8"))
    next_payload = build_next_payload(progress_payload, args.limit)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(next_payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_next_md(next_payload), encoding="utf-8")

    print(f"business-execution-next: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
