#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdetkit import day74_distribution_scaling_closeout as d74


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Day 74 distribution scaling closeout contract"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d74.build_day74_distribution_scaling_closeout_summary(root)
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
            / "docs/artifacts/day74-distribution-scaling-closeout-pack/evidence/day74-execution-summary.json"
        )
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
        print("day74-distribution-scaling-closeout contract check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("day74-distribution-scaling-closeout contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
