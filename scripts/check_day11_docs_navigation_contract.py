from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
DAY11_REPORT = Path("docs/day-11-ultra-upgrade-report.md")
DAY11_ARTIFACT = Path("docs/artifacts/day11-docs-navigation-sample.md")

README_EXPECTED = [
    "## 🧭 Day 11 ultra: docs navigation tune-up",
    "python -m sdetkit docs-nav --format text --strict",
    "python -m sdetkit docs-nav --write-defaults --format json --strict",
    "python scripts/check_day11_docs_navigation_contract.py",
    "docs/day-11-ultra-upgrade-report.md",
]

DOCS_INDEX_EXPECTED = [
    "[🧭 Day 11 ultra report](day-11-ultra-upgrade-report.md)",
    "## Day 11 ultra upgrades (docs navigation tune-up)",
    "sdetkit docs-nav --format text --strict",
    "sdetkit docs-nav --write-defaults --format json --strict",
    "Run first command in under 60 seconds",
    "Validate docs links and anchors before publishing",
    "Ship a first contribution with deterministic quality gates",
]

DOCS_CLI_EXPECTED = [
    "## docs-nav",
    "sdetkit docs-nav --format markdown --output docs/artifacts/day11-docs-navigation-sample.md",
    "--strict",
    "--write-defaults",
]

REPORT_EXPECTED = [
    "Day 11 big upgrade",
    "python -m sdetkit docs-nav --format json --strict",
    "python -m sdetkit docs-nav --write-defaults --format json --strict",
    "scripts/check_day11_docs_navigation_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Day 11 docs navigation tune-up",
    "- Score: **100.0** (12/12)",
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main() -> int:
    errors: list[str] = []
    required = [README, DOCS_INDEX, DOCS_CLI, DAY11_REPORT, DAY11_ARTIFACT]
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f'{README}: missing "{m}"' for m in _missing(README, README_EXPECTED))
        errors.extend(
            f'{DOCS_INDEX}: missing "{m}"' for m in _missing(DOCS_INDEX, DOCS_INDEX_EXPECTED)
        )
        errors.extend(f'{DOCS_CLI}: missing "{m}"' for m in _missing(DOCS_CLI, DOCS_CLI_EXPECTED))
        errors.extend(
            f'{DAY11_REPORT}: missing "{m}"' for m in _missing(DAY11_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{DAY11_ARTIFACT}: missing "{m}"' for m in _missing(DAY11_ARTIFACT, ARTIFACT_EXPECTED)
        )

    if errors:
        print("day11-docs-navigation-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day11-docs-navigation-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
