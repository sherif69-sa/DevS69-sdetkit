from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
LANE_REPORT = Path("docs/impact-9-ultra-upgrade-report.md")
LANE_ARTIFACT = Path("docs/artifacts/triage-templates-sample-9.md")
ISSUE_CONFIG = Path(".github/ISSUE_TEMPLATE/config.yml")

README_EXPECTED = [
    '## 🧩  ultra: contribution templates',
    "python -m sdetkit triage-templates --format text --strict",
    "python -m sdetkit triage-templates --write-defaults --format json --strict",
    "docs/impact-9-ultra-upgrade-report.md",
]

DOCS_INDEX_EXPECTED = [
    '##  ultra upgrades (contribution templates)',
    "sdetkit triage-templates --format text --strict",
    "sdetkit triage-templates --write-defaults --format json --strict",
    "artifacts/triage-templates-sample-9.md",
]

DOCS_CLI_EXPECTED = [
    "## triage-templates",
    "--write-defaults",
    "--root",
    "sdetkit triage-templates --format markdown --output docs/artifacts/triage-templates-sample-9.md",
]

REPORT_EXPECTED = [
    ' big upgrade',
    "python -m sdetkit triage-templates --format json --strict",
    "python -m sdetkit triage-templates --write-defaults --format json --strict",
    "scripts/check_contribution_templates_contract_9.py",
]

ISSUE_CONFIG_EXPECTED = [
    "blank_issues_enabled: false",
    "contact_links:",
    "Security report",
    "Questions / discussion",
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main() -> int:
    errors: list[str] = []
    for path in [README, DOCS_INDEX, DOCS_CLI, LANE_REPORT, LANE_ARTIFACT, ISSUE_CONFIG]:
        if not path.exists():
            errors.append(f"missing required file: {path}")

    if not errors:
        errors.extend(f'{README}: missing "{m}"' for m in _missing(README, README_EXPECTED))
        errors.extend(
            f'{DOCS_INDEX}: missing "{m}"' for m in _missing(DOCS_INDEX, DOCS_INDEX_EXPECTED)
        )
        errors.extend(f'{DOCS_CLI}: missing "{m}"' for m in _missing(DOCS_CLI, DOCS_CLI_EXPECTED))
        errors.extend(
            f'{LANE_REPORT}: missing "{m}"' for m in _missing(LANE_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{ISSUE_CONFIG}: missing "{m}"' for m in _missing(ISSUE_CONFIG, ISSUE_CONFIG_EXPECTED)
        )

    if errors:
        print("contribution-templates-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("contribution-templates-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
