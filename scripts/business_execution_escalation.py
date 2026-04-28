#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-escalation.v1"


def build_escalation_payload(
    week1: dict[str, Any],
    progress: dict[str, Any],
    next_payload: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    week1_status = str(week1.get("status", "needs-owner-assignment"))
    gate = str(progress.get("gate_decision", {}).get("status", "fail"))
    completion = float(progress.get("task_summary", {}).get("completion_percent", 0.0))
    pending_tasks = [task for task in next_payload.get("next_tasks", []) if isinstance(task, str)]
    owners = week1.get("owners", week1.get("owner_assignments", {}))

    reasons: list[str] = []
    decision = "none"
    if week1_status != "go":
        decision = "watch"
        reasons.append("Week-1 owners are not fully assigned yet.")
    if gate == "fail":
        decision = "escalate"
        reasons.append("Execution gate is failing.")
    elif gate == "conditional-pass" and decision != "escalate":
        decision = "watch"
        reasons.append("Execution is in progress and requires daily follow-up.")
    if completion < 50 and decision != "escalate":
        decision = "watch"
        reasons.append("Completion is below 50 percent.")

    owners_to_ping: list[str] = []
    if isinstance(owners, dict):
        owners_to_ping = [
            str(owner).strip()
            for owner in owners.values()
            if isinstance(owner, str) and str(owner).strip() and str(owner).strip().upper() != "TBD"
        ]
    if decision == "escalate" and not owners_to_ping:
        owners_to_ping = ["Program Owner"]

    recommended_actions: list[str] = []
    if decision == "escalate":
        recommended_actions = [
            "Assign all missing owners immediately.",
            "Run `make business-execution-go-gate` after owner updates.",
            "Review and execute the top pending tasks today.",
        ]
    elif decision == "watch":
        recommended_actions = [
            "Close the top pending tasks by end of day.",
            "Refresh progress and handoff artifacts.",
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "week1_status": week1_status,
        "progress_gate": gate,
        "completion_percent": completion,
        "handoff_recommended_command": handoff.get("recommended_command"),
        "pending_count": len(pending_tasks),
        "pending_tasks": pending_tasks,
        "decision": decision,
        "reasons": reasons,
        "owners_to_ping": owners_to_ping,
        "recommended_actions": recommended_actions,
    }


def render_escalation_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Business Execution Escalation",
        "",
        f"- Decision: {payload.get('decision')}",
        f"- Week-1 status: {payload.get('week1_status')}",
        f"- Progress gate: {payload.get('progress_gate')}",
        f"- Completion percent: {payload.get('completion_percent')}",
        f"- Pending tasks: {payload.get('pending_count')}",
        "",
        "## Reasons",
    ]
    reasons = payload.get("reasons") or []
    if reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- No escalation reasons.")
    lines.extend(["", "## Owners to ping"])
    owners = payload.get("owners_to_ping") or []
    if owners:
        for owner in owners:
            lines.append(f"- {owner}")
    else:
        lines.append("- None")
    lines.extend(["", "## Recommended actions"])
    actions = payload.get("recommended_actions") or []
    if actions:
        for action in actions:
            lines.append(f"- [ ] {action}")
    else:
        lines.append("- No immediate escalation actions.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate business execution escalation artifact.")
    parser.add_argument("--week1", default="build/business-execution/business-execution-week1.json")
    parser.add_argument(
        "--progress", default="build/business-execution/business-execution-week1-progress.json"
    )
    parser.add_argument(
        "--next",
        dest="next_json",
        default="build/business-execution/business-execution-week1-next.json",
    )
    parser.add_argument(
        "--handoff", default="build/business-execution/business-execution-handoff.json"
    )
    parser.add_argument(
        "--out-json", default="build/business-execution/business-execution-escalation.json"
    )
    parser.add_argument(
        "--out-md", default="build/business-execution/business-execution-escalation.md"
    )
    args = parser.parse_args(argv)

    week1 = json.loads(Path(args.week1).read_text(encoding="utf-8"))
    progress = json.loads(Path(args.progress).read_text(encoding="utf-8"))
    next_payload = json.loads(Path(args.next_json).read_text(encoding="utf-8"))
    handoff = json.loads(Path(args.handoff).read_text(encoding="utf-8"))
    payload = build_escalation_payload(week1, progress, next_payload, handoff)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_escalation_md(payload), encoding="utf-8")

    print(f"business-execution-escalation: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
