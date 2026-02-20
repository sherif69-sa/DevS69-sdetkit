#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY14_REPORT = Path("docs/day-14-ultra-upgrade-report.md")
DAY14_ARTIFACT = Path("docs/artifacts/day14-weekly-review-sample.md")
DAY14_SIGNALS = Path("docs/artifacts/day14-growth-signals.json")
DAY7_SIGNALS = Path("docs/artifacts/day7-growth-signals.json")
DAY14_PACK_CHECKLIST = Path("docs/artifacts/day14-weekly-pack/day14-closeout-checklist.md")
DAY14_PACK_SCORECARD = Path("docs/artifacts/day14-weekly-pack/day14-kpi-scorecard.json")
DAY14_PACK_PLAN = Path("docs/artifacts/day14-weekly-pack/day14-blocker-action-plan.md")
WEEKLY_MODULE = Path("src/sdetkit/weekly_review.py")

README_EXPECTED = [
    "## 📈 Day 14 ultra: weekly review #2",
    "python -m sdetkit weekly-review --week 2 --format text --signals-file docs/artifacts/day14-growth-signals.json --previous-signals-file docs/artifacts/day7-growth-signals.json",
    "python -m sdetkit weekly-review --week 2 --emit-pack-dir docs/artifacts/day14-weekly-pack --signals-file docs/artifacts/day14-growth-signals.json --previous-signals-file docs/artifacts/day7-growth-signals.json --format json --strict",
    "python scripts/check_day14_weekly_review_contract.py",
    "docs/day-14-ultra-upgrade-report.md",
]

INDEX_EXPECTED = [
    "Day 14 ultra upgrades (weekly review #2 + KPI checkpoint)",
    "sdetkit weekly-review --week 2 --format text --signals-file docs/artifacts/day14-growth-signals.json --previous-signals-file docs/artifacts/day7-growth-signals.json",
    "artifacts/day14-weekly-review-sample.md",
    "artifacts/day14-weekly-pack/day14-closeout-checklist.md",
]

CLI_EXPECTED = [
    "sdetkit weekly-review --week 2 --format json --signals-file docs/artifacts/day14-growth-signals.json --previous-signals-file docs/artifacts/day7-growth-signals.json",
    "sdetkit weekly-review --week 2 --emit-pack-dir docs/artifacts/day14-weekly-pack --format json --strict",
    "Useful flags: `--root`, `--week`, `--signals-file`, `--previous-signals-file`, `--emit-pack-dir`, `--strict`, `--format`, `--output`.",
]

REPORT_EXPECTED = [
    "Day 14 big upgrade",
    "src/sdetkit/weekly_review.py",
    "tests/test_weekly_review.py",
    "docs/artifacts/day14-weekly-pack/*",
    "python scripts/check_day14_weekly_review_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Day 14 Weekly Review #2",
    "## What shipped (Day 8-13)",
    "## Week-two growth signals",
    "## Week-over-week deltas",
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main() -> int:
    errors: list[str] = []
    required = [
        README,
        DOCS_INDEX,
        DOCS_CLI,
        DAY14_REPORT,
        DAY14_ARTIFACT,
        DAY14_SIGNALS,
        DAY7_SIGNALS,
        DAY14_PACK_CHECKLIST,
        DAY14_PACK_SCORECARD,
        DAY14_PACK_PLAN,
        WEEKLY_MODULE,
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f'{README}: missing "{m}"' for m in _missing(README, README_EXPECTED))
        errors.extend(f'{DOCS_INDEX}: missing "{m}"' for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f'{DOCS_CLI}: missing "{m}"' for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(
            f'{DAY14_REPORT}: missing "{m}"' for m in _missing(DAY14_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{DAY14_ARTIFACT}: missing "{m}"' for m in _missing(DAY14_ARTIFACT, ARTIFACT_EXPECTED)
        )

    if errors:
        print("day14-weekly-review-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day14-weekly-review-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
