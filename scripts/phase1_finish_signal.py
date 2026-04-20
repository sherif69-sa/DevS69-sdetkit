#!/usr/bin/env python3
"""Compute a simple finish signal for Phase 1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_finish_signal(control_loop: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    completion = float(control_loop.get("completion_percent", 0) or 0)
    ready = bool(dashboard.get("ready_to_close", False))
    gate_ok = bool(dashboard.get("completion_gate", {}).get("ok", False))

    if ready and gate_ok:
        status = "complete"
    elif completion >= 80:
        status = "near_finish"
    elif completion >= 50:
        status = "in_progress"
    else:
        status = "early"

    blockers = dashboard.get("completion_gate", {}).get("failing_required_checks", [])
    if not isinstance(blockers, list):
        blockers = []

    return {
        "schema_version": "sdetkit.phase1_finish_signal.v1",
        "status": status,
        "completion_percent": completion,
        "ready_to_close": ready,
        "gate_ok": gate_ok,
        "blocking_required_checks": blockers,
        "next_step": dashboard.get("next_step", "make phase1-next"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute Phase 1 finish signal.")
    parser.add_argument(
        "--control-loop", default="build/phase1-baseline/phase1-control-loop-report.json"
    )
    parser.add_argument(
        "--dashboard", default="build/phase1-baseline/phase1-completion-dashboard.json"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    control = _load_json(Path(args.control_loop))
    dashboard = _load_json(Path(args.dashboard))

    if not control or not dashboard:
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_finish_signal.v1",
            "reason": "missing control-loop or dashboard artifact",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase1-finish-signal: FAIL ({payload['reason']})")
        return 1

    payload = build_finish_signal(control, dashboard)
    payload["ok"] = True

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"phase1-finish-signal: {payload['status']}")
        print(f"- completion_percent: {payload['completion_percent']}")
        print(f"- next_step: {payload['next_step']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
