from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY19_PAGE = Path("docs/integrations-release-readiness-board.md")
DAY19_REPORT = Path("docs/day-19-ultra-upgrade-report.md")
DAY19_ARTIFACT = Path("docs/artifacts/day19-release-readiness-board-sample.md")
DAY19_PACK_SUMMARY = Path(
    "docs/artifacts/day19-release-readiness-pack/day19-release-readiness-summary.json"
)
DAY19_PACK_SCORECARD = Path(
    "docs/artifacts/day19-release-readiness-pack/day19-release-readiness-scorecard.md"
)
DAY19_PACK_CHECKLIST = Path(
    "docs/artifacts/day19-release-readiness-pack/day19-release-readiness-checklist.md"
)
DAY19_PACK_VALIDATION = Path(
    "docs/artifacts/day19-release-readiness-pack/day19-validation-commands.md"
)
DAY19_PACK_DECISION = Path("docs/artifacts/day19-release-readiness-pack/day19-release-decision.md")
DAY19_EVIDENCE = Path(
    "docs/artifacts/day19-release-readiness-pack/evidence/day19-execution-summary.json"
)
MODULE = Path("src/sdetkit/release_readiness_board.py")

README_EXPECTED = [
    "## 🧭 Day 19 ultra: release readiness board",
    "python -m sdetkit release-readiness-board --format text",
    "python -m sdetkit release-readiness-board --format json --strict",
    "python -m sdetkit release-readiness-board --emit-pack-dir docs/artifacts/day19-release-readiness-pack --format json --strict",
    "python -m sdetkit release-readiness-board --execute --evidence-dir docs/artifacts/day19-release-readiness-pack/evidence --format json --strict",
    "python scripts/check_day19_release_readiness_board_contract.py",
]

INDEX_EXPECTED = [
    "Day 19 ultra upgrades (release readiness board)",
    "sdetkit release-readiness-board --format json --strict",
    "artifacts/day19-release-readiness-board-sample.md",
]

CLI_EXPECTED = [
    "## release-readiness-board",
    "--day18-summary",
    "--day14-summary",
    "--min-release-score",
    "--write-defaults",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]

PAGE_EXPECTED = [
    "# Release readiness board (Day 19)",
    "## Score model",
    "## Fast verification commands",
    "## Execution evidence mode",
]

REPORT_EXPECTED = ["Day 19 big upgrade", "release score", "strict", "--execute --evidence-dir"]
SUMMARY_EXPECTED = [
    '"name": "day19-release-readiness-board"',
    '"release_score":',
    '"strict_all_green":',
]
EVIDENCE_EXPECTED = ['"name": "day19-release-readiness-execution"', '"total_commands": 3']


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
        DAY19_PAGE,
        DAY19_REPORT,
        DAY19_ARTIFACT,
        DAY19_PACK_SUMMARY,
        DAY19_PACK_SCORECARD,
        DAY19_PACK_CHECKLIST,
        DAY19_PACK_VALIDATION,
        DAY19_PACK_DECISION,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(DAY19_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(f"{DAY19_PAGE}: missing '{m}'" for m in _missing(DAY19_PAGE, PAGE_EXPECTED))
        errors.extend(
            f"{DAY19_REPORT}: missing '{m}'" for m in _missing(DAY19_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{DAY19_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(DAY19_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{DAY19_EVIDENCE}: missing '{m}'"
                for m in _missing(DAY19_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("day19-release-readiness-board-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day19-release-readiness-board-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
