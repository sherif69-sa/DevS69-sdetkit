#!/usr/bin/env python3
"""Close out Phase 1 and prune it from the active strategic plan when complete."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_phase(sequence: list[dict[str, Any]], phase_id: int) -> dict[str, Any] | None:
    for phase in sequence:
        if phase.get("id") == phase_id:
            return phase
    return None


def closeout_phase1(status_path: Path, plan_path: Path, archive_dir: Path) -> dict[str, Any]:
    if not status_path.is_file():
        return {
            "ok": False,
            "schema_version": "sdetkit.phase1_closeout.v1",
            "reason": f"missing status file: {status_path}",
        }

    status_payload = _load_json(status_path)
    if not bool(status_payload.get("ok", False)):
        return {
            "ok": False,
            "schema_version": "sdetkit.phase1_closeout.v1",
            "reason": "phase1 status is incomplete; complete phase1 before closeout",
            "hard_blockers": status_payload.get("hard_blockers", []),
        }

    if not plan_path.is_file():
        return {
            "ok": False,
            "schema_version": "sdetkit.phase1_closeout.v1",
            "reason": f"missing plan file: {plan_path}",
        }

    plan_payload = _load_json(plan_path)
    phase_sequence = plan_payload.get("phase_sequence", [])
    if not isinstance(phase_sequence, list):
        phase_sequence = []

    phase1 = _find_phase(phase_sequence, 1)
    phase2 = _find_phase(phase_sequence, 2)
    if phase1 is None:
        return {
            "ok": False,
            "schema_version": "sdetkit.phase1_closeout.v1",
            "reason": "phase 1 is not present in active phase_sequence",
        }
    if phase2 is None:
        return {
            "ok": False,
            "schema_version": "sdetkit.phase1_closeout.v1",
            "reason": "phase 2 is missing; cannot advance current phase",
        }

    timestamp = _utc_now()
    archive_path = archive_dir / f"phase1-closeout-plan-snapshot-{timestamp[:10]}.json"
    _write_json(archive_path, plan_payload)

    new_sequence = [phase for phase in phase_sequence if phase.get("id") != 1]
    completed = list(plan_payload.get("completed_phases", []))
    completed.append(
        {
            "id": 1,
            "name": phase1.get("name"),
            "completed_at": timestamp,
            "status_source": str(status_path),
        }
    )

    plan_payload["phase_sequence"] = new_sequence
    plan_payload["completed_phases"] = completed
    plan_payload["current_phase"] = {
        "id": phase2.get("id"),
        "name": phase2.get("name"),
        "objective": phase2.get("objective", ""),
        "window": phase2.get("window", "Weeks 3-6"),
    }
    plan_payload["updated_at"] = timestamp

    _write_json(plan_path, plan_payload)

    return {
        "ok": True,
        "schema_version": "sdetkit.phase1_closeout.v1",
        "closed_phase": 1,
        "new_current_phase": plan_payload["current_phase"],
        "archived_plan": str(archive_path),
        "plan": str(plan_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Close Phase 1 and prune it from active plan.")
    parser.add_argument("--status-json", default="build/phase1-baseline/phase1-status.json")
    parser.add_argument("--plan", default="plans/strategic-execution-model-2026.json")
    parser.add_argument("--archive-dir", default="plans/archive")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    result = closeout_phase1(
        status_path=Path(args.status_json),
        plan_path=Path(args.plan),
        archive_dir=Path(args.archive_dir),
    )

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result.get("ok", False):
            print("phase1-closeout: COMPLETE")
            print(f"- archived plan: {result['archived_plan']}")
            nxt = result.get("new_current_phase", {})
            print(f"- next active phase: {nxt.get('id')} ({nxt.get('name')})")
        else:
            print(f"phase1-closeout: FAIL ({result.get('reason', 'unknown error')})")

    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
