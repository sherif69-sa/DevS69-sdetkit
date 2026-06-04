#!/usr/bin/env python3
"""Close out baseline and prune it from the active strategic plan when complete."""

from __future__ import annotations

import argparse
import datetime as _sdetkit_datetime
import json
from datetime import datetime
from pathlib import Path
from typing import Any

UTC = getattr(_sdetkit_datetime, "UTC", _sdetkit_datetime.timezone.utc)  # noqa: UP017


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


def complete_baseline_flow(status_path: Path, plan_path: Path, archive_dir: Path) -> dict[str, Any]:
    if not status_path.is_file():
        return {
            "ok": False,
            "schema_version": "sdetkit.baseline_completion.v1",
            "reason": f"missing status file: {status_path}",
        }

    status_payload = _load_json(status_path)
    if not bool(status_payload.get("ok", False)):
        return {
            "ok": False,
            "schema_version": "sdetkit.baseline_completion.v1",
            "reason": "baseline status is incomplete; complete baseline before completion report",
            "hard_blockers": status_payload.get("hard_blockers", []),
        }

    if not plan_path.is_file():
        return {
            "ok": False,
            "schema_version": "sdetkit.baseline_completion.v1",
            "reason": f"missing plan file: {plan_path}",
        }

    plan_payload = _load_json(plan_path)
    phase_sequence = plan_payload.get("phase_sequence", [])
    if not isinstance(phase_sequence, list):
        phase_sequence = []

    baseline = _find_phase(phase_sequence, 1)
    release_readiness = _find_phase(phase_sequence, 2)
    if baseline is None:
        return {
            "ok": False,
            "schema_version": "sdetkit.baseline_completion.v1",
            "reason": "baseline is not present in active phase_sequence",
        }
    if release_readiness is None:
        return {
            "ok": False,
            "schema_version": "sdetkit.baseline_completion.v1",
            "reason": "release readiness is missing; cannot advance current phase",
        }

    timestamp = _utc_now()
    archive_path = archive_dir / f"baseline-completion-report-plan-snapshot-{timestamp[:10]}.json"
    _write_json(archive_path, plan_payload)

    new_sequence = [phase for phase in phase_sequence if phase.get("id") != 1]
    completed = list(plan_payload.get("completed_phases", []))
    completed.append(
        {
            "id": 1,
            "name": baseline.get("name"),
            "completed_at": timestamp,
            "status_source": str(status_path),
        }
    )

    plan_payload["phase_sequence"] = new_sequence
    plan_payload["completed_phases"] = completed
    plan_payload["current_phase"] = {
        "id": release_readiness.get("id"),
        "name": release_readiness.get("name"),
        "objective": release_readiness.get("objective", ""),
        "window": release_readiness.get("window", "Weeks 3-6"),
    }
    plan_payload["updated_at"] = timestamp

    _write_json(plan_path, plan_payload)

    return {
        "ok": True,
        "schema_version": "sdetkit.baseline_completion.v1",
        "closed_phase": 1,
        "new_current_phase": plan_payload["current_phase"],
        "archived_plan": str(archive_path),
        "plan": str(plan_path),
    }


def baseline(status_path: Path, plan_path: Path, archive_dir: Path) -> dict[str, Any]:
    """Compatibility wrapper for the historical baseline completion helper."""
    return complete_baseline_flow(status_path, plan_path, archive_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Close baseline and prune it from active plan.")
    parser.add_argument("--status-json", default="build/baseline/baseline-status.json")
    parser.add_argument("--plan", default="plans/strategic-execution-model-2026.json")
    parser.add_argument("--archive-dir", default="plans/archive")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    result = complete_baseline_flow(
        status_path=Path(args.status_json),
        plan_path=Path(args.plan),
        archive_dir=Path(args.archive_dir),
    )

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result.get("ok", False):
            print("baseline-completion-report: COMPLETE")
            print(f"- archived plan: {result['archived_plan']}")
            nxt = result.get("new_current_phase", {})
            print(f"- next active phase: {nxt.get('id')} ({nxt.get('name')})")
        else:
            print(f"baseline-completion-report: FAIL ({result.get('reason', 'unknown error')})")

    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
