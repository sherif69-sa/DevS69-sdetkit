#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "docs/contribution-quality-report.md",
        ROOT / "docs/artifacts/contribution-quality-report-sample.md",
        ROOT
        / "docs/artifacts/contribution-quality-report-pack/contribution-quality-report-summary.json",
        ROOT
        / "docs/artifacts/contribution-quality-report-pack/contribution-quality-report-action-plan.md",
        ROOT
        / "docs/artifacts/contribution-quality-report-pack/contribution-quality-report-remediation-checklist.md",
        ROOT / "docs/artifacts/contribution-quality-growth-signals.json",
        ROOT / "src/sdetkit/quality_contribution_delta.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        print(
            f"Missing Cycle 17 contribution-quality contract files: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    module = (ROOT / "src/sdetkit/quality_contribution_delta.py").read_text(encoding="utf-8")
    for snippet in [
        '"name": "contribution-quality-report"',
        'prog="sdetkit contribution-quality-report"',
        "--current-signals-file",
        "--previous-signals-file",
    ]:
        if snippet not in module:
            print(f"contribution-quality-report contract missing: {snippet}", file=sys.stderr)
            return 1

    print("quality-contribution-delta-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
