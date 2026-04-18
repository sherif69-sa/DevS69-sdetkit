#!/usr/bin/env python3
"""Retire Phase 1 planning state and persist flow-first manifest after closeout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.phase1_closeout_and_prune_plan import closeout_phase1

FLOW_COMMANDS = [
    "make phase-current",
    "make phase1-baseline",
    "make phase1-status",
    "make phase1-next",
    "make phase1-ops-snapshot",
    "make phase1-dashboard",
    "make phase1-weekly-pack",
    "make phase1-control-loop",
    "make phase1-run-all",
    "make phase1-artifact-set",
    "make phase1-telemetry",
    "make phase1-finish-signal",
    "make phase1-next-pass",
    "make phase1-blocker-register",
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def retire_phase1_plan(status_json: Path, plan_json: Path, archive_dir: Path, flow_manifest: Path) -> dict[str, Any]:
    closeout = closeout_phase1(status_json, plan_json, archive_dir)
    if not closeout.get("ok", False):
        return {
            "ok": False,
            "schema_version": "sdetkit.phase1_retire_plan.v1",
            "reason": closeout.get("reason", "closeout failed"),
            "closeout": closeout,
        }

    manifest = {
        "schema_version": "sdetkit.phase1_flow_manifest.v1",
        "phase1_plan_retired": True,
        "status_source": str(status_json),
        "archived_plan": closeout.get("archived_plan"),
        "active_plan": closeout.get("plan"),
        "flow_commands": FLOW_COMMANDS,
        "next_phase": closeout.get("new_current_phase", {}),
    }
    _write_json(flow_manifest, manifest)

    return {
        "ok": True,
        "schema_version": "sdetkit.phase1_retire_plan.v1",
        "flow_manifest": str(flow_manifest),
        "closeout": closeout,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retire Phase 1 plan into a flow-first manifest.")
    parser.add_argument("--status-json", default="build/phase1-baseline/phase1-status.json")
    parser.add_argument("--plan", default="plans/strategic-execution-model-2026.json")
    parser.add_argument("--archive-dir", default="plans/archive")
    parser.add_argument("--flow-manifest", default="plans/phase1-flow-manifest.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    result = retire_phase1_plan(
        status_json=Path(args.status_json),
        plan_json=Path(args.plan),
        archive_dir=Path(args.archive_dir),
        flow_manifest=Path(args.flow_manifest),
    )

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result.get("ok", False):
            print("phase1-retire-plan: COMPLETE")
            print(f"- flow_manifest: {result['flow_manifest']}")
        else:
            print(f"phase1-retire-plan: FAIL ({result.get('reason', 'unknown error')})")

    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
