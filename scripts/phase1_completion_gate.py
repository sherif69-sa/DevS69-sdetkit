#!/usr/bin/env python3
"""Decide if Phase 1 is complete from baseline summary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_REQUIRED = [
    "doctor",
    "enterprise_contracts",
    "primary_docs_map",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--required-check", action="append", default=None)
    ap.add_argument("--allow-fail", action="append", default=None)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args()

    summary_path = Path(ns.summary)
    if not summary_path.is_file():
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_completion_gate.v1",
            "reason": f"missing summary file: {summary_path}",
            "required_checks": [],
            "allow_fail": [],
            "failing_required_checks": [],
        }
        if ns.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase1-completion-gate: FAIL (missing summary file: {summary_path})")
        return 1

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = payload.get("checks", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []

    required = ns.required_check or list(DEFAULT_REQUIRED)
    allow_fail = set(ns.allow_fail or ["ruff", "pytest", "gate_fast", "gate_release"])

    by_id: dict[str, bool] = {}
    for row in rows:
        if isinstance(row, dict):
            check_id = str(row.get("id", ""))
            check_ok = bool(row.get("ok", False))
            if check_id:
                by_id[check_id] = check_ok

    failing_required = [check_id for check_id in required if not by_id.get(check_id, False)]
    unknown_required = [check_id for check_id in required if check_id not in by_id]

    blocked_nonrequired = [
        check_id
        for check_id, check_ok in by_id.items()
        if not check_ok and check_id not in required and check_id not in allow_fail
    ]

    ok = not failing_required and not unknown_required and not blocked_nonrequired
    result = {
        "ok": ok,
        "schema_version": "sdetkit.phase1_completion_gate.v1",
        "summary": str(summary_path),
        "required_checks": required,
        "allow_fail": sorted(allow_fail),
        "failing_required_checks": failing_required,
        "missing_required_checks": unknown_required,
        "blocked_nonrequired_checks": sorted(blocked_nonrequired),
    }

    if ns.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if ok:
            print("phase1-completion-gate: OK")
        else:
            print("phase1-completion-gate: FAIL")
            if failing_required:
                print(f"- failing required checks: {', '.join(failing_required)}")
            if unknown_required:
                print(f"- missing required checks: {', '.join(unknown_required)}")
            if blocked_nonrequired:
                print(f"- blocked by non-allowlisted checks: {', '.join(sorted(blocked_nonrequired))}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
