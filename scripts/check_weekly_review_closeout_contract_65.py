#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdetkit import weekly_review_closeout_65 as d65


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Day 65 weekly review closeout contract (legacy alias)"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d65.build_weekly_review_closeout_summary(root)
    errors: list[str] = []

    if payload["summary"]["activation_score"] < 95:
        errors.append(f"activation_score too low: {payload['summary']['activation_score']}")
    if not payload["summary"]["strict_pass"]:
        errors.append("strict_pass is false")

    failed = [check["check_id"] for check in payload["checks"] if not check["passed"]]
    if failed:
        errors.append(f"failed checks: {failed}")

    if not ns.skip_evidence:
        evidence = (
            root
            / "docs/artifacts/weekly-review-closeout-pack-2/evidence/weekly-review-closeout-execution-summary-2.json"
        )
        if not evidence.exists():
            legacy_evidence = (
                root
                / "docs/artifacts/weekly-review-closeout-2-pack/evidence/day65-execution-summary.json"
            )
            if legacy_evidence.exists():
                evidence = legacy_evidence
        if not evidence.exists():
            errors.append(f"missing evidence summary: {evidence}")
        else:
            try:
                summary = json.loads(evidence.read_text(encoding="utf-8"))
                if int(summary.get("total_commands", 0)) < 3:
                    errors.append("expected >=3 executed commands")
            except Exception as exc:  # pragma: no cover
                errors.append(f"failed to parse evidence summary: {exc}")

    if errors:
        print("weekly-review-closeout-2 contract check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("weekly-review-closeout-2 contract check passed")
    return 0


if __name__ == "main_":
    raise SystemExit(main())
