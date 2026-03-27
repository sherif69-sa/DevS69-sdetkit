from __future__ import annotations

import argparse
import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
RELEASE_READINESS_PAGE = Path("docs/release-readiness.md")
RELEASE_READINESS_REPORT = Path("docs/release-readiness-report.md")
RELEASE_READINESS_ARTIFACT = Path("docs/release-readiness.md")
RELEASE_READINESS_PACK_SUMMARY = Path(
    "docs/artifacts/release-readiness-pack/release-readiness-summary.json"
)
RELEASE_READINESS_PACK_SCORECARD = Path(
    "docs/artifacts/release-readiness-pack/release-readiness-scorecard.md"
)
RELEASE_READINESS_PACK_CHECKLIST = Path(
    "docs/artifacts/release-readiness-pack/release-readiness-checklist.md"
)
RELEASE_READINESS_PACK_VALIDATION = Path(
    "docs/artifacts/release-readiness-pack/release-readiness-validation-commands.md"
)
RELEASE_READINESS_PACK_DECISION = Path("docs/artifacts/release-readiness-pack/release-decision.md")
RELEASE_READINESS_EVIDENCE = Path(
    "docs/artifacts/release-readiness-pack/evidence/release-readiness-execution-summary.json"
)
MODULE = Path("src/sdetkit/release_readiness.py")

README_EXPECTED = [
    "## Release readiness",
    "python -m sdetkit release-readiness --format text",
    "python -m sdetkit release-readiness --format json --strict",
    "python -m sdetkit release-readiness --emit-pack-dir docs/artifacts/release-readiness-pack --format json --strict",
    "python -m sdetkit release-readiness --execute --evidence-dir docs/artifacts/release-readiness-pack/evidence --format json --strict",
    "python scripts/check_release_readiness_contract.py",
]

INDEX_EXPECTED = [
    "Release readiness",
    "sdetkit release-readiness --format json --strict",
    "artifacts/release-readiness-pack/release-readiness-summary.json",
]

CLI_EXPECTED = [
    "## release-readiness",
    "--reliability-summary",
    "--weekly-review-summary",
    "--min-release-score",
    "--write-defaults",
    "--execute",
    "--evidence-dir",
    "--timeout-sec",
    "--emit-pack-dir",
]

PAGE_EXPECTED = [
    "# Release readiness board",
    "## Score model",
    "## Fast verification commands",
    "## Execution evidence mode",
]

REPORT_EXPECTED = [
    "Release readiness report",
    "release score",
    "strict",
    "--execute --evidence-dir",
]
SUMMARY_EXPECTED = [
    '"name": "release-readiness"',
    '"release_score":',
    '"strict_all_green":',
]
EVIDENCE_EXPECTED = ['"name": "release-readiness-execution"', '"total_commands": 3']


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
        RELEASE_READINESS_PAGE,
        RELEASE_READINESS_REPORT,
        RELEASE_READINESS_ARTIFACT,
        RELEASE_READINESS_PACK_SUMMARY,
        RELEASE_READINESS_PACK_SCORECARD,
        RELEASE_READINESS_PACK_CHECKLIST,
        RELEASE_READINESS_PACK_VALIDATION,
        RELEASE_READINESS_PACK_DECISION,
        MODULE,
    ]
    if not ns.skip_evidence:
        required.append(RELEASE_READINESS_EVIDENCE)

    errors: list[str] = []
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f"{README}: missing '{m}'" for m in _missing(README, README_EXPECTED))
        errors.extend(f"{DOCS_INDEX}: missing '{m}'" for m in _missing(DOCS_INDEX, INDEX_EXPECTED))
        errors.extend(f"{DOCS_CLI}: missing '{m}'" for m in _missing(DOCS_CLI, CLI_EXPECTED))
        errors.extend(
            f"{RELEASE_READINESS_PAGE}: missing '{m}'"
            for m in _missing(RELEASE_READINESS_PAGE, PAGE_EXPECTED)
        )
        errors.extend(
            f"{RELEASE_READINESS_REPORT}: missing '{m}'"
            for m in _missing(RELEASE_READINESS_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f"{RELEASE_READINESS_PACK_SUMMARY}: missing '{m}'"
            for m in _missing(RELEASE_READINESS_PACK_SUMMARY, SUMMARY_EXPECTED)
        )
        if not ns.skip_evidence:
            errors.extend(
                f"{RELEASE_READINESS_EVIDENCE}: missing '{m}'"
                for m in _missing(RELEASE_READINESS_EVIDENCE, EVIDENCE_EXPECTED)
            )

    if errors:
        print("release-readiness-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("release-readiness-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
