#!/usr/bin/env python3
"""Generate deterministic next actions from Phase 1 status payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status-json", required=True)
    ap.add_argument("--out", default=None, help="Optional output path for next-actions JSON payload.")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args()

    status_path = Path(ns.status_json)
    if not status_path.is_file():
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_next_actions.v1",
            "reason": f"missing status file: {status_path}",
            "next_actions": [
                "Run: python scripts/phase1_status_report.py --format json --out build/phase1-baseline/phase1-status.json"
            ],
        }
        if ns.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("phase1-next-actions: FAIL")
            print(f"- missing status file: {status_path}")
        return 1

    status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    not_yet = status_payload.get("not_yet", []) if isinstance(status_payload, dict) else []
    hard_blockers = status_payload.get("hard_blockers", []) if isinstance(status_payload, dict) else []
    if not isinstance(not_yet, list):
        not_yet = []
    if not isinstance(hard_blockers, list):
        hard_blockers = []

    next_actions: list[str] = []
    for item in not_yet:
        text = str(item)
        if text.startswith("python_version>=3.11"):
            next_actions.append("Use Python 3.11+ environment then rerun: make phase1-baseline")
        elif text == "optional_check_ok::ruff":
            next_actions.append("Run lint remediation: ruff check . --fix")
        elif text == "optional_check_ok::pytest":
            next_actions.append("Run test lane: PYTHONPATH=src pytest -q")
        elif text.startswith("required_check_ok::"):
            check_id = text.split("::", 1)[1]
            next_actions.append(f"Rerun baseline and inspect failing check: {check_id}")
        elif text.startswith("baseline_summary_exists"):
            next_actions.append("Generate baseline summary: make phase1-baseline")

    deduped: list[str] = []
    seen: set[str] = set()
    for action in next_actions:
        if action not in seen:
            seen.add(action)
            deduped.append(action)

    ok = len(hard_blockers) == 0
    payload = {
        "ok": ok,
        "schema_version": "sdetkit.phase1_next_actions.v1",
        "status_json": str(status_path),
        "hard_blockers": hard_blockers,
        "actions_are_advisory": ok and len(deduped) > 0,
        "next_actions": deduped,
    }

    if ns.out:
        out_path = Path(ns.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-next-actions: READY" if ok else "phase1-next-actions: ACTIONS_REQUIRED")
        for action in deduped:
            print(f"- {action}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
