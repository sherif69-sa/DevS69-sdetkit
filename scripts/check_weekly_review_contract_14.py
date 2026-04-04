#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "docs/ultra-upgrade-report-14.md",
        ROOT / "docs/artifacts/weekly-review-sample-14.md",
        ROOT / "docs/artifacts/weekly-review-growth-signals.json",
        ROOT / "docs/artifacts/growth-signals-baseline.json",
        ROOT / "docs/artifacts/weekly-pack-14/closeout-checklist-14.md",
        ROOT / "docs/artifacts/weekly-pack-14/kpi-scorecard-14.json",
        ROOT / "docs/artifacts/weekly-pack-14/blocker-action-plan-14.md",
        ROOT / "src/sdetkit/weekly_review.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        print(f"Missing Cycle 14 weekly-review contract files: {', '.join(missing)}", file=sys.stderr)
        return 1

    weekly = (ROOT / "src/sdetkit/weekly_review.py").read_text(encoding="utf-8")
    for snippet in ["choices=[1, 2, 3]", "def _emit_week2_pack", "--emit-pack-dir"]:
        if snippet not in weekly:
            print(f"weekly-review contract missing: {snippet}", file=sys.stderr)
            return 1

    print("weekly-review-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
