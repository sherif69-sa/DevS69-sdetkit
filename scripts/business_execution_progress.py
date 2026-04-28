#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-progress.v1"


def _flatten_plan(plan: dict[str, list[str]]) -> list[str]:
    ordered_keys = ("day_1", "day_2_3", "day_4_5")
    tasks: list[str] = []
    for key in ordered_keys:
        tasks.extend(plan.get(key, []))
    return tasks


def build_progress(
    week1_payload: dict[str, Any], done_items: set[str], owner_gate_mode: str = "relaxed"
) -> dict[str, Any]:
    plan = week1_payload.get("week_1_execution_plan", {})
    tasks = _flatten_plan(plan if isinstance(plan, dict) else {})
    rows = [{"task": task, "done": task in done_items} for task in tasks]
    completed = sum(1 for row in rows if row["done"])
    total = len(rows)
    percent = round((completed / total) * 100, 2) if total else 0.0

    base_status = str(week1_payload.get("status", "needs-owner-assignment"))
    if base_status != "go":
        if owner_gate_mode == "strict":
            gate = "fail"
            reason = "Owner assignment is incomplete."
        else:
            gate = "conditional-pass"
            reason = "Owner assignment is incomplete, but execution can continue while assigning owners."
    elif completed == total and total > 0:
        gate = "pass"
        reason = "All week-1 execution tasks are complete."
    else:
        gate = "conditional-pass"
        reason = "Execution in progress."

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": week1_payload.get("schema_version"),
        "status": base_status,
        "task_summary": {"completed": completed, "total": total, "completion_percent": percent},
        "tasks": rows,
        "gate_decision": {"status": gate, "reason": reason},
    }


def render_progress_md(progress_payload: dict[str, Any]) -> str:
    summary = progress_payload["task_summary"]
    lines = [
        "# Business Execution Week-1 Progress",
        "",
        f"- Status: {progress_payload['status']}",
        f"- Completed: {summary['completed']}/{summary['total']} ({summary['completion_percent']}%)",
        f"- Gate: {progress_payload['gate_decision']['status']}",
        f"- Reason: {progress_payload['gate_decision']['reason']}",
        "",
        "## Tasks",
    ]
    for row in progress_payload["tasks"]:
        box = "[x]" if row["done"] else "[ ]"
        lines.append(f"- {box} {row['task']}")
    lines.append("")
    return "\n".join(lines)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track business execution week-1 progress and gate status.")
    parser.add_argument(
        "--week1",
        default="build/business-execution/business-execution-week1.json",
        help="Path to week-1 execution artifact.",
    )
    parser.add_argument(
        "--done",
        action="append",
        default=[],
        help="Task text to mark as completed (repeatable).",
    )
    parser.add_argument(
        "--out-json",
        default="build/business-execution/business-execution-week1-progress.json",
    )
    parser.add_argument(
        "--out-md",
        default="build/business-execution/business-execution-week1-progress.md",
    )
    parser.add_argument(
        "--history",
        default="build/business-execution/business-execution-week1-progress-history.jsonl",
        help="Append each progress run as one JSON line.",
    )
    parser.add_argument(
        "--history-rollup-out",
        default="build/business-execution/business-execution-week1-progress-rollup.json",
        help="Write aggregate trend rollup for the history file.",
    )
    parser.add_argument(
        "--owner-gate-mode",
        choices=("relaxed", "strict"),
        default="relaxed",
        help="Use strict mode to fail when owners are unassigned, or relaxed mode to keep execution moving.",
    )
    args = parser.parse_args(argv)

    week1_payload = json.loads(Path(args.week1).read_text(encoding="utf-8"))
    done_items = {item.strip() for item in args.done if item.strip()}
    progress_payload = build_progress(week1_payload, done_items, owner_gate_mode=args.owner_gate_mode)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(progress_payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_progress_md(progress_payload), encoding="utf-8")

    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_event = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "status": progress_payload["status"],
        "gate_status": progress_payload["gate_decision"]["status"],
        "completion_percent": progress_payload["task_summary"]["completion_percent"],
        "completed": progress_payload["task_summary"]["completed"],
        "total": progress_payload["task_summary"]["total"],
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_event) + "\n")

    history_rows = _load_jsonl(history_path)
    gate_counts: dict[str, int] = {"pass": 0, "conditional-pass": 0, "fail": 0}
    for row in history_rows:
        gate = str(row.get("gate_status", ""))
        if gate in gate_counts:
            gate_counts[gate] += 1
    latest = history_rows[-1] if history_rows else None
    rollup = {
        "schema_version": "sdetkit.business-execution-progress-rollup.v1",
        "history_records": len(history_rows),
        "gate_counts": gate_counts,
        "latest": latest,
    }
    rollup_path = Path(args.history_rollup_out)
    rollup_path.parent.mkdir(parents=True, exist_ok=True)
    rollup_path.write_text(json.dumps(rollup, indent=2) + "\n", encoding="utf-8")

    print(f"business-execution-progress: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
