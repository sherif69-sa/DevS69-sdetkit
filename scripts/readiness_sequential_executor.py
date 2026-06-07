#!/usr/bin/env python3
"""Print execution guidance from the Phase 1 workflow contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PLAN = Path("plans/strategic-execution-model-2026.json")
DEFAULT_STATUS = Path("build/phase1-baseline/phase1-status.json")


def _load_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "error": f"missing workflow contract file: {path}",
            "schema_version": "sdetkit.phase_sequential_executor.v1",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "plan": data,
        "schema_version": "sdetkit.phase_sequential_executor.v1",
    }


def _phase_from_plan(plan: dict[str, Any], phase_id: int | None) -> dict[str, Any] | None:
    phase_sequence = plan.get("phase_sequence", [])
    if phase_id is None:
        current_phase = plan.get("current_phase", {})
        phase_id = current_phase.get("id")
    if phase_id is None:
        return None
    for item in phase_sequence:
        if item.get("id") == phase_id:
            return item
    return None


def _status_progress(status_path: Path) -> dict[str, Any]:
    if not status_path.is_file():
        return {
            "status_file": str(status_path),
            "available": False,
            "progress_percent": 0,
            "accomplished_count": 0,
            "remaining_count": 0,
        }
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    accomplished = payload.get("accomplished", []) if isinstance(payload, dict) else []
    not_yet = payload.get("not_yet", []) if isinstance(payload, dict) else []
    if not isinstance(accomplished, list):
        accomplished = []
    if not isinstance(not_yet, list):
        not_yet = []
    total = len(accomplished) + len(not_yet)
    percent = round((len(accomplished) / total) * 100, 1) if total else 0
    return {
        "status_file": str(status_path),
        "available": True,
        "phase1_ok": bool(payload.get("ok", False)),
        "progress_percent": percent,
        "accomplished_count": len(accomplished),
        "remaining_count": len(not_yet),
        "hard_blockers": payload.get("hard_blockers", []),
    }


def build_payload(
    plan_path: Path,
    phase_id: int | None = None,
    status_path: Path = DEFAULT_STATUS,
) -> dict[str, Any]:
    loaded = _load_plan(plan_path)
    if not loaded["ok"]:
        return loaded

    plan = loaded["plan"]
    phase = _phase_from_plan(plan, phase_id)
    if phase is None:
        return {
            "ok": False,
            "schema_version": "sdetkit.phase_sequential_executor.v1",
            "error": "phase not found in workflow contract",
            "requested_phase": phase_id,
            "available_phases": [item.get("id") for item in plan.get("phase_sequence", [])],
        }

    return {
        "ok": True,
        "schema_version": "sdetkit.phase_sequential_executor.v1",
        "plan_id": plan.get("plan_id"),
        "current_phase": phase,
        "control_loop": plan.get("control_loop", []),
        "phase_handoff_rule": plan.get("phase_handoff_rule", ""),
        "next_commands": phase.get("now_actions", []),
        "progress": _status_progress(status_path),
    }


def _render_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok", False):
        return f"phase-sequential: FAIL ({payload.get('error', 'unknown error')})"

    phase = payload.get("current_phase", {})
    lines = [
        "phase-sequential: READY",
        f"phase: {phase.get('id')} - {phase.get('name', 'unknown')}",
        "control loop:",
    ]
    for item in payload.get("control_loop", []):
        lines.append(f"- {item}")

    commands = payload.get("next_commands", [])
    if commands:
        lines.append("next commands:")
        for cmd in commands:
            lines.append(f"- {cmd}")

    handoff = payload.get("phase_handoff_rule")
    if handoff:
        lines.append(f"handoff rule: {handoff}")
    progress = payload.get("progress", {})
    if isinstance(progress, dict) and progress.get("available"):
        lines.append(
            "progress: "
            f"{progress.get('progress_percent', 0)}% "
            f"({progress.get('accomplished_count', 0)} done / {progress.get('remaining_count', 0)} remaining)"
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute Phase 1 workflow guidance.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--status-json", default=str(DEFAULT_STATUS))
    parser.add_argument("--phase", type=int)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payload = build_payload(
        Path(args.plan), phase_id=args.phase, status_path=Path(args.status_json)
    )
    ok = bool(payload.get("ok", False))

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_text(payload))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
