#!/usr/bin/env python3
"""Emit Phase 1 status report: accomplished vs pending."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_CHECKS = [
    "gate_fast",
    "gate_release",
    "doctor",
    "enterprise_contracts",
    "primary_docs_map",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="build/phase1-baseline/phase1-baseline-summary.json")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args()

    summary_path = Path(ns.summary)

    accomplished: list[str] = []
    pending: list[str] = []

    py_ok = sys.version_info >= (3, 11)
    if py_ok:
        accomplished.append(f"python_version>=3.11 ({sys.version.split()[0]})")
    else:
        pending.append(f"python_version>=3.11 (detected {sys.version.split()[0]})")

    if summary_path.is_file():
        accomplished.append(f"baseline_summary_exists ({summary_path})")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        checks = payload.get("checks", []) if isinstance(payload, dict) else []
        by_id = {str(row.get('id')): bool(row.get('ok', False)) for row in checks if isinstance(row, dict)}
        for check_id in REQUIRED_CHECKS:
            if by_id.get(check_id, False):
                accomplished.append(f"required_check_ok::{check_id}")
            else:
                pending.append(f"required_check_ok::{check_id}")

        for optional in ("ruff", "pytest"):
            if optional in by_id:
                if by_id[optional]:
                    accomplished.append(f"optional_check_ok::{optional}")
                else:
                    pending.append(f"optional_check_ok::{optional}")
            else:
                pending.append(f"optional_check_present::{optional}")
    else:
        pending.append(f"baseline_summary_exists ({summary_path})")
        pending.extend([f"required_check_ok::{check_id}" for check_id in REQUIRED_CHECKS])

    done = not pending

    result = {
        "ok": done,
        "schema_version": "sdetkit.phase1_status.v1",
        "summary": str(summary_path),
        "accomplished": accomplished,
        "not_yet": pending,
    }

    if ns.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("phase1-status: COMPLETE" if done else "phase1-status: INCOMPLETE")
        print("accomplished:")
        for item in accomplished:
            print(f"- {item}")
        print("not_yet:")
        for item in pending:
            print(f"- {item}")

    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
