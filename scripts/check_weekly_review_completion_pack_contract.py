#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "docs/roadmap/reports/ultra-upgrade-report-20.md",
        ROOT / "docs/roadmap/reports/ultra-upgrade-report-21.md",
        ROOT / "docs/artifacts/weekly-review-sample-21.md",
        ROOT / "docs/artifacts/weekly-review-growth-signals.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing Cycle 21 contract files: {', '.join(missing)}")

    weekly_review = (ROOT / "src/sdetkit/weekly_review.py").read_text(encoding="utf-8")
    if "choices=[1, 2, 3]" not in weekly_review:
        raise SystemExit("weekly-review parser must support --week 3")
    if "def _emit_week3_pack" not in weekly_review:
        raise SystemExit("weekly-review must implement a week-3 closeout pack emitter")

    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
