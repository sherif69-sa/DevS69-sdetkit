from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY17_REPORT = Path("docs/day-17-ultra-upgrade-report.md")
DAY17_ARTIFACT = Path("docs/artifacts/day17-quality-contribution-delta-sample.md")
DAY17_PACK_SUMMARY = Path("docs/artifacts/day17-delta-pack/day17-delta-summary.json")
DAY17_PACK_ACTION = Path("docs/artifacts/day17-delta-pack/day17-contribution-action-plan.md")
DAY17_PACK_CHECKLIST = Path("docs/artifacts/day17-delta-pack/day17-remediation-checklist.md")
DAY17_SIGNALS = Path("docs/artifacts/day17-growth-signals.json")
MODULE = Path("src/sdetkit/quality_contribution_delta.py")

README_EXPECTED = [
    "## 🧮 Day 17 ultra: quality + contribution deltas",
    "python -m sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format json --strict",
    "python -m sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --emit-pack-dir docs/artifacts/day17-delta-pack --format json --strict",
    "python scripts/check_day17_quality_contribution_delta_contract.py",
]

INDEX_EXPECTED = [
    "Day 17 ultra upgrades (quality + contribution deltas)",
    "sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format json --strict",
    "artifacts/day17-quality-contribution-delta-sample.md",
]

CLI_EXPECTED = [
    "## quality-contribution-delta",
    "--current-signals-file",
    "--previous-signals-file",
    "--min-traffic-delta",
    "--min-stars-delta",
    "--min-discussions-delta",
    "--min-blocker-fixes-delta",
]

REPORT_EXPECTED = [
    "Day 17 big upgrade",
    "velocity score",
    "strict delta gates",
]

SUMMARY_EXPECTED = [
    '"name": "day17-quality-contribution-delta"',
    '"velocity_score":',
    '"stability_score":',
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main() -> int:
    required = [
        README,
        DOCS_INDEX,
        DOCS_CLI,
        DAY17_REPORT,
        DAY17_ARTIFACT,
        DAY17_PACK_SUMMARY,
        DAY17_PACK_ACTION,
        DAY17_PACK_CHECKLIST,
        DAY17_SIGNALS,
        MODULE,
    ]
    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(
            f"{DAY17_REPORT}: missing '{m}'" for m in _missing(DAY17_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{DAY17_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(DAY17_PACK_SUMMARY, SUMMARY_EXPECTED)
        )

    if errors:
        print("day17-quality-contribution-delta-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day17-quality-contribution-delta-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
