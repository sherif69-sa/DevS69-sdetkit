from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY18_PAGE = Path("docs/integrations-reliability-evidence-pack.md")
DAY18_REPORT = Path("docs/day-18-ultra-upgrade-report.md")
DAY18_ARTIFACT = Path("docs/artifacts/day18-reliability-evidence-pack-sample.md")
DAY18_PACK_SUMMARY = Path("docs/artifacts/day18-reliability-pack/day18-reliability-summary.json")
DAY18_PACK_SCORECARD = Path("docs/artifacts/day18-reliability-pack/day18-reliability-scorecard.md")
DAY18_PACK_CHECKLIST = Path("docs/artifacts/day18-reliability-pack/day18-reliability-checklist.md")
DAY18_PACK_VALIDATION = Path("docs/artifacts/day18-reliability-pack/day18-validation-commands.md")
DAY18_EVIDENCE = Path("docs/artifacts/day18-reliability-pack/evidence/day18-execution-summary.json")
MODULE = Path("src/sdetkit/reliability_evidence_pack.py")

README_EXPECTED = [
    "## 🧱 Day 18 ultra: reliability evidence pack",
    "python -m sdetkit reliability-evidence-pack --format text",
    "python -m sdetkit reliability-evidence-pack --format json --strict",
    "python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/day18-reliability-pack --format json --strict",
    "python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/day18-reliability-pack/evidence --format json --strict",
    "python scripts/check_day18_reliability_evidence_pack_contract.py",
]

INDEX_EXPECTED = [
    "Day 18 ultra upgrades (reliability evidence pack)",
    "sdetkit reliability-evidence-pack --format json --strict",
    "artifacts/day18-reliability-evidence-pack-sample.md",
]

CLI_EXPECTED = [
    "## reliability-evidence-pack",
    "--day15-summary",
    "--day16-summary",
    "--day17-summary",
    "--min-reliability-score",
    "--write-defaults",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]

PAGE_EXPECTED = [
    "# Reliability evidence pack (Day 18)",
    "## Reliability score model",
    "## Fast verification commands",
    "## Execution evidence mode",
]

REPORT_EXPECTED = [
    "Day 18 big upgrade",
    "reliability score",
    "strict gates",
    "--execute --evidence-dir",
]

SUMMARY_EXPECTED = [
    '"name": "day18-reliability-evidence-pack"',
    '"reliability_score":',
    '"strict_all_green":',
]

EVIDENCE_EXPECTED = [
    '"name": "day18-reliability-execution"',
    '"total_commands": 3',
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-evidence", action="store_true")
    ns = ap.parse_args(argv)

    required = [
        README,
        DOCS_INDEX,
        DOCS_CLI,
        DAY18_PAGE,
        DAY18_REPORT,
        DAY18_ARTIFACT,
        DAY18_PACK_SUMMARY,
        DAY18_PACK_SCORECARD,
        DAY18_PACK_CHECKLIST,
        DAY18_PACK_VALIDATION,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(DAY18_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(f"{DAY18_PAGE}: missing '{m}'" for m in _missing(DAY18_PAGE, PAGE_EXPECTED))
        errors.extend(
            f"{DAY18_REPORT}: missing '{m}'" for m in _missing(DAY18_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{DAY18_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(DAY18_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{DAY18_EVIDENCE}: missing '{m}'"
                for m in _missing(DAY18_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("day18-reliability-evidence-pack-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day18-reliability-evidence-pack-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
