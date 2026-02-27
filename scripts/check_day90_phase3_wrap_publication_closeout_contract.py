#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdetkit import day90_phase3_wrap_publication_closeout as d90


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Day 90 phase-3 wrap publication closeout contract"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d90.build_day90_phase3_wrap_publication_closeout_summary(root)
    errors: list[str] = []

    if not payload.get("summary", {}).get("strict_pass", False):
        errors.append("summary.strict_pass is false")

    if payload.get("summary", {}).get("activation_score", 0) < 95:
        errors.append("activation_score below 95")

    if payload.get("summary", {}).get("critical_failures"):
        errors.append("critical_failures is not empty")

    if not ns.skip_evidence:
        evidence = (
            root
            / "docs/artifacts/day90-phase3-wrap-publication-closeout-pack/evidence/day90-execution-summary.json"
        )
        if not evidence.exists():
            errors.append(f"missing evidence summary: {evidence}")
        else:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if int(data.get("total_commands", 0)) < 3:
                errors.append("evidence total_commands below 3")

    if errors:
        print("day90-phase3-wrap-publication-closeout contract check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("day90-phase3-wrap-publication-closeout contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
