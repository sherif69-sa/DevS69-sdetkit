#!/usr/bin/env python3
"""Retire baseline planning state and persist flow-first manifest after completion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.baseline_completion_and_prune_plan import complete_baseline_flow

FLOW_COMMANDS = [
    "make phase-current",
    "make baseline-baseline",
    "make baseline-status",
    "make baseline-next",
    "make baseline-ops-snapshot",
    "make baseline-dashboard",
    "make baseline-weekly-pack",
    "make baseline-control-loop",
    "make baseline-run-all",
    "make baseline-artifact-set",
    "make baseline-telemetry",
    "make baseline-readiness-signal",
    "make baseline-followup-pass",
    "make baseline-blocker-register",
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def retire_baseline_plan(
    status_json: Path, plan_json: Path, archive_dir: Path, flow_manifest: Path
) -> dict[str, Any]:
    completion = complete_baseline_flow(status_json, plan_json, archive_dir)
    if not completion.get("ok", False):
        return {
            "ok": False,
            "schema_version": "sdetkit.baseline_transition_plan.v1",
            "reason": completion.get("reason", "completion report failed"),
            "completion": completion,
        }

    manifest = {
        "schema_version": "sdetkit.baseline_flow_manifest.v1",
        "baseline_plan_retired": True,
        "status_source": str(status_json),
        "archived_plan": completion.get("archived_plan"),
        "active_plan": completion.get("plan"),
        "flow_commands": FLOW_COMMANDS,
        "next_phase": completion.get("new_current_phase", {}),
    }
    _write_json(flow_manifest, manifest)

    return {
        "ok": True,
        "schema_version": "sdetkit.baseline_transition_plan.v1",
        "flow_manifest": str(flow_manifest),
        "completion": completion,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retire baseline plan into a flow-first manifest.")
    parser.add_argument("--status-json", default="build/baseline/baseline-status.json")
    parser.add_argument("--plan", default="plans/strategic-execution-model-2026.json")
    parser.add_argument("--archive-dir", default="plans/archive")
    parser.add_argument("--flow-manifest", default="plans/baseline-flow-manifest.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    result = retire_baseline_plan(
        status_json=Path(args.status_json),
        plan_json=Path(args.plan),
        archive_dir=Path(args.archive_dir),
        flow_manifest=Path(args.flow_manifest),
    )

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result.get("ok", False):
            print("baseline-transition-plan: COMPLETE")
            print(f"- flow_manifest: {result['flow_manifest']}")
        else:
            print(f"baseline-transition-plan: FAIL ({result.get('reason', 'unknown error')})")

    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
