from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
LANE_PAGE = Path("docs/reliability-evidence-pack.md")
LANE_REPORT = Path("docs/reliability-evidence-report.md")
LANE_ARTIFACT = Path("docs/reliability-evidence-pack.md")
LANE_PACK_SUMMARY = Path(
    "docs/artifacts/reliability-evidence-pack/reliability-evidence-summary.json"
)
LANE_PACK_SCORECARD = Path(
    "docs/artifacts/reliability-evidence-pack/reliability-evidence-scorecard.md"
)
LANE_PACK_CHECKLIST = Path(
    "docs/artifacts/reliability-evidence-pack/reliability-evidence-checklist.md"
)
LANE_PACK_VALIDATION = Path(
    "docs/artifacts/reliability-evidence-pack/reliability-evidence-validation-commands.md"
)
LANE_EVIDENCE = Path(
    "docs/artifacts/reliability-evidence-pack/evidence/reliability-evidence-execution-summary.json"
)
MODULE = Path("src/sdetkit/reliability_evidence_pack.py")

README_EXPECTED = [
    "## Reliability evidence pack",
    "python -m sdetkit reliability-evidence-pack --format text",
    "python -m sdetkit reliability-evidence-pack --format json --strict",
    "python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/reliability-evidence-pack --format json --strict",
    "python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/reliability-evidence-pack/evidence --format json --strict",
    "python scripts/check_reliability_evidence_pack_contract.py",
]

INDEX_EXPECTED = [
    "Reliability evidence pack",
    "sdetkit reliability-evidence-pack --format json --strict",
    "artifacts/reliability-evidence-pack/reliability-evidence-summary.json",
]

CLI_EXPECTED = [
    "## reliability-evidence-pack",
    "--github-actions-summary",
    "--gitlab-ci-summary",
    "--contribution-quality-summary",
    "--min-reliability-score",
    "--write-defaults",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]

PAGE_EXPECTED = [
    "# Reliability evidence pack",
    "## Reliability score model",
    "## Fast verification commands",
    "## Execution evidence mode",
]

REPORT_EXPECTED = [
    "Reliability evidence report",
    "reliability score",
    "strict gates",
    "--execute --evidence-dir",
]

SUMMARY_EXPECTED = [
    '"name": "reliability-evidence-pack"',
    '"reliability_score":',
    '"strict_all_green":',
]

EVIDENCE_EXPECTED = [
    '"name": "reliability-evidence-execution"',
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
        LANE_PAGE,
        LANE_REPORT,
        LANE_ARTIFACT,
        LANE_PACK_SUMMARY,
        LANE_PACK_SCORECARD,
        LANE_PACK_CHECKLIST,
        LANE_PACK_VALIDATION,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(LANE_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(f"{LANE_PAGE}: missing '{m}'" for m in _missing(LANE_PAGE, PAGE_EXPECTED))
        errors.extend(
            f"{LANE_REPORT}: missing '{m}'" for m in _missing(LANE_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{LANE_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(LANE_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{LANE_EVIDENCE}: missing '{m}'"
                for m in _missing(LANE_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("reliability-evidence-pack-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("reliability-evidence-pack-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
