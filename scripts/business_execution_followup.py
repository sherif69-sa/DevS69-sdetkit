#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-followup.v1"


def build_followup_payload(
    progress: dict[str, Any],
    next_payload: dict[str, Any],
    escalation: dict[str, Any],
    window_hours: int,
) -> dict[str, Any]:
    gate_status = str(progress.get("gate_decision", {}).get("status", "conditional-pass"))
    escalation_decision = str(escalation.get("decision", "watch"))
    next_tasks = [task for task in next_payload.get("next_tasks", []) if isinstance(task, str)]
    immediate_actions = [f"Complete: {task}" for task in next_tasks]

    if escalation_decision == "escalate":
        immediate_actions.extend(
            [
                "Review escalation reasons with the operator now.",
                "Execute escalation recommended actions before next checkpoint.",
            ]
        )
    if not immediate_actions:
        immediate_actions.append("No pending tasks. Keep monitoring execution health.")

    keep_moving = gate_status in {"conditional-pass", "fail"} or escalation_decision in {"watch", "escalate"}
    recommended_command = next_payload.get("recommended_command")
    if not isinstance(recommended_command, str) or not recommended_command.strip():
        recommended_command = "make business-execution-pipeline"

    return {
        "schema_version": SCHEMA_VERSION,
        "progress_gate": gate_status,
        "escalation_decision": escalation_decision,
        "window_hours": max(1, window_hours),
        "pending_count": len(next_tasks),
        "next_tasks": next_tasks,
        "immediate_actions": immediate_actions,
        "recommended_command": recommended_command,
        "keep_moving": keep_moving,
    }


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


def render_followup_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Business Execution Follow-up Loop",
        "",
        f"- Progress gate: {payload.get('progress_gate')}",
        f"- Escalation decision: {payload.get('escalation_decision')}",
        f"- Follow-up window (hours): {payload.get('window_hours')}",
        f"- Pending tasks: {payload.get('pending_count')}",
        f"- Keep moving: {payload.get('keep_moving')}",
        f"- Next checkpoint: {payload.get('next_checkpoint_at')}",
        f"- Checkpoint status: {payload.get('checkpoint_status')}",
        f"- Checkpoint due in (hours): {payload.get('checkpoint_due_in_hours')}",
        f"- Checkpoint command: {payload.get('checkpoint_command')}",
        "",
        "## Immediate actions",
    ]
    for action in payload.get("immediate_actions", []):
        lines.append(f"- [ ] {action}")
    lines.extend(["", "## Recommended command", f"`{payload.get('recommended_command')}`", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate continuous follow-up actions from current execution artifacts.")
    parser.add_argument("--progress", default="build/business-execution/business-execution-week1-progress.json")
    parser.add_argument("--next", dest="next_json", default="build/business-execution/business-execution-week1-next.json")
    parser.add_argument("--escalation", default="build/business-execution/business-execution-escalation.json")
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument(
        "--history",
        default="build/business-execution/business-execution-followup-history.jsonl",
        help="Append follow-up snapshots as JSONL events.",
    )
    parser.add_argument(
        "--history-rollup-out",
        default="build/business-execution/business-execution-followup-rollup.json",
        help="Write follow-up history rollup summary.",
    )
    parser.add_argument("--out-json", default="build/business-execution/business-execution-followup.json")
    parser.add_argument("--out-md", default="build/business-execution/business-execution-followup.md")
    args = parser.parse_args(argv)

    progress = json.loads(Path(args.progress).read_text(encoding="utf-8"))
    next_payload = json.loads(Path(args.next_json).read_text(encoding="utf-8"))
    escalation = json.loads(Path(args.escalation).read_text(encoding="utf-8"))
    payload = build_followup_payload(progress, next_payload, escalation, window_hours=args.window_hours)

    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_event = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "progress_gate": payload["progress_gate"],
        "escalation_decision": payload["escalation_decision"],
        "pending_count": payload["pending_count"],
        "keep_moving": payload["keep_moving"],
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_event) + "\n")

    history_rows = _load_jsonl(history_path)
    decision_counts: dict[str, int] = {"none": 0, "watch": 0, "escalate": 0}
    for row in history_rows:
        decision = str(row.get("escalation_decision", ""))
        if decision in decision_counts:
            decision_counts[decision] += 1
    payload["history_records"] = len(history_rows)
    payload["decision_counts"] = decision_counts
    payload["latest_recorded_at"] = history_rows[-1]["recorded_at"] if history_rows else None
    latest_recorded_at = payload["latest_recorded_at"]
    if isinstance(latest_recorded_at, str):
        latest_dt = datetime.fromisoformat(latest_recorded_at)
        next_checkpoint_dt = latest_dt + timedelta(hours=payload["window_hours"])
        payload["next_checkpoint_at"] = next_checkpoint_dt.isoformat()
        now_utc = datetime.now(UTC)
        due_in_hours = round((next_checkpoint_dt - now_utc).total_seconds() / 3600, 2)
        payload["checkpoint_due_in_hours"] = due_in_hours
        if now_utc >= next_checkpoint_dt:
            payload["checkpoint_status"] = "due"
            payload["checkpoint_command"] = "make business-execution-followup"
        else:
            payload["checkpoint_status"] = "on-track"
            payload["checkpoint_command"] = "make business-execution-followup"
    else:
        payload["next_checkpoint_at"] = None
        payload["checkpoint_status"] = "on-track"
        payload["checkpoint_due_in_hours"] = float(payload["window_hours"])
        payload["checkpoint_command"] = "make business-execution-followup"

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_followup_md(payload), encoding="utf-8")

    rollup = {
        "schema_version": "sdetkit.business-execution-followup-rollup.v1",
        "history_records": len(history_rows),
        "decision_counts": decision_counts,
        "latest": history_rows[-1] if history_rows else None,
        "next_checkpoint_at": payload["next_checkpoint_at"],
        "checkpoint_status": payload["checkpoint_status"],
        "checkpoint_due_in_hours": payload["checkpoint_due_in_hours"],
        "checkpoint_command": payload["checkpoint_command"],
    }
    rollup_path = Path(args.history_rollup_out)
    rollup_path.parent.mkdir(parents=True, exist_ok=True)
    rollup_path.write_text(json.dumps(rollup, indent=2) + "\n", encoding="utf-8")

    print(f"business-execution-followup: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
