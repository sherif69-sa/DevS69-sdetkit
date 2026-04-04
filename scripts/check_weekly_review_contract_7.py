#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
LANE_REPORT = Path("docs/impact-7-ultra-upgrade-report.md")
LANE_ARTIFACT = Path("docs/artifacts/weekly-review-sample-7.md")
WEEKLY_MODULE = Path("src/sdetkit/weekly_review.py")

REQUIRED_README_SNIPPETS = [
    "## 📊 Day 7 ultra: weekly review #1",
    "python -m sdetkit weekly-review --format text",
    "python -m sdetkit weekly-review --format markdown --output docs/artifacts/weekly-review-sample-7.md",
    "docs/impact-7-ultra-upgrade-report.md",
]

REQUIRED_INDEX_SNIPPETS = [
    "Day 7 ultra upgrade report",
    "sdetkit weekly-review --format text",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 7 big upgrade",
    "src/sdetkit/weekly_review.py",
    "tests/test_weekly_review.py",
    "python scripts/check_weekly_review_contract_7.py",
]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    readme = _read(README)
    docs_index = _read(DOCS_INDEX)
    report = _read(LANE_REPORT)

    for s in REQUIRED_README_SNIPPETS:
        if s not in readme:
            errors.append(f"missing README snippet: {s}")

    for s in REQUIRED_INDEX_SNIPPETS:
        if s not in docs_index:
            errors.append(f"missing docs/index snippet: {s}")

    for s in REQUIRED_REPORT_SNIPPETS:
        if s not in report:
            errors.append(f"missing Day 7 report snippet: {s}")

    for p in [LANE_REPORT, LANE_ARTIFACT, WEEKLY_MODULE]:
        if not p.exists():
            errors.append(f"missing required file: {p}")

    if errors:
        print("weekly-review-contract check failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1

    print("weekly-review-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
