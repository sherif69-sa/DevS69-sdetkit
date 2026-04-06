from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
CONTRIBUTING = Path("CONTRIBUTING.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DOCS_CONTRIBUTING = Path("docs/contributing.md")
LANE_REPORT = Path("docs/impact-10-ultra-upgrade-report.md")
FIRST_CONTRIBUTION_ARTIFACT = Path("docs/artifacts/first-contribution-checklist-sample.md")

README_EXPECTED = [
    '## ✅  ultra: first-contribution checklist',
    "python -m sdetkit first-contribution --format text --strict",
    "python -m sdetkit first-contribution --write-defaults --format json --strict",
    "python scripts/check_first_contribution_contract_10.py",
    "docs/impact-10-ultra-upgrade-report.md",
]

CONTRIBUTING_EXPECTED = [
    '## 0)  first-contribution checklist',
    "Fork the repository and clone your fork locally.",
    "Create a branch named `feat/<topic>` or `fix/<topic>`.",
    "Run full quality gates (`pre-commit`, `quality.sh`, docs build) before opening a PR.",
]

DOCS_INDEX_EXPECTED = [
    '##  ultra upgrades (first-contribution checklist)',
    "sdetkit first-contribution --format text --strict",
    "sdetkit first-contribution --write-defaults --format json --strict",
    "artifacts/first-contribution-checklist-sample.md",
]

DOCS_CLI_EXPECTED = [
    "## first-contribution",
    "sdetkit first-contribution --format markdown --output docs/artifacts/first-contribution-checklist-sample.md",
    "--strict",
    "--write-defaults",
]

DOCS_CONTRIBUTING_EXPECTED = [
    '##  first-contribution checklist',
    "sdetkit first-contribution --format text --strict",
    "sdetkit first-contribution --write-defaults --format json --strict",
]

REPORT_EXPECTED = [
    ' big upgrade',
    "python -m sdetkit first-contribution --format json --strict",
    "python -m sdetkit first-contribution --write-defaults --format json --strict",
    "scripts/check_first_contribution_contract_10.py",
]

ARTIFACT_EXPECTED = [
    '#  first-contribution checklist',
    "- Score: **100.0** (14/14)",
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main() -> int:
    errors: list[str] = []
    required = [
        README,
        CONTRIBUTING,
        DOCS_INDEX,
        DOCS_CLI,
        DOCS_CONTRIBUTING,
        LANE_REPORT,
        FIRST_CONTRIBUTION_ARTIFACT,
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f'{README}: missing "{m}"' for m in _missing(README, README_EXPECTED))
        errors.extend(
            f'{CONTRIBUTING}: missing "{m}"' for m in _missing(CONTRIBUTING, CONTRIBUTING_EXPECTED)
        )
        errors.extend(
            f'{DOCS_INDEX}: missing "{m}"' for m in _missing(DOCS_INDEX, DOCS_INDEX_EXPECTED)
        )
        errors.extend(f'{DOCS_CLI}: missing "{m}"' for m in _missing(DOCS_CLI, DOCS_CLI_EXPECTED))
        errors.extend(
            f'{DOCS_CONTRIBUTING}: missing "{m}"'
            for m in _missing(DOCS_CONTRIBUTING, DOCS_CONTRIBUTING_EXPECTED)
        )
        errors.extend(
            f'{LANE_REPORT}: missing "{m}"' for m in _missing(LANE_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{FIRST_CONTRIBUTION_ARTIFACT}: missing "{m}"'
            for m in _missing(FIRST_CONTRIBUTION_ARTIFACT, ARTIFACT_EXPECTED)
        )

    if errors:
        print("first-contribution-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("first-contribution-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
