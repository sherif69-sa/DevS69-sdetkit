#!/usr/bin/env python3
"""Calculate Phase 2 completion progress from workflow artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_progress(
    phase2_status: dict[str, Any], phase2_complete: dict[str, Any]
) -> dict[str, Any]:
    milestones: list[dict[str, Any]] = []

    status_ok = bool(phase2_status.get("ok", False))
    milestones.append({"id": "phase2_start_status_ok", "ok": status_ok})

    complete_steps = phase2_complete.get("steps", [])
    if not isinstance(complete_steps, list):
        complete_steps = []
    complete_ok = bool(phase2_complete.get("ok", False))
    milestones.append({"id": "phase2_complete_workflow_ok", "ok": complete_ok})

    for marker in (
        "phase2-hardening-closeout",
        "phase2-wrap-handoff-closeout",
    ):
        found = any(
            marker in str(step.get("command", "")) and bool(step.get("ok", False))
            for step in complete_steps
        )
        milestones.append({"id": f"step::{marker}", "ok": found})

    total = len(milestones)
    done = sum(1 for m in milestones if m["ok"])
    percent = round((done / total) * 100, 1) if total else 0.0

    return {
        "schema_version": "sdetkit.phase2_progress.v1",
        "ok": done == total and total > 0,
        "milestones_completed": done,
        "milestones_total": total,
        "completion_percent": percent,
        "milestones": milestones,
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 2 progress report.")
    parser.add_argument("--phase2-status", default="build/phase2-start/phase2-status.json")
    parser.add_argument(
        "--phase2-complete", default="build/phase2-complete/phase2-complete-summary.json"
    )
    parser.add_argument("--out", default="build/phase2-complete/phase2-progress.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payload = build_progress(_load(Path(args.phase2_status)), _load(Path(args.phase2_complete)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"phase2-progress: {payload['completion_percent']}% ({payload['milestones_completed']}/{payload['milestones_total']})"
        )
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
