from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
USE_CASE_PAGE = Path("docs/use-cases-enterprise-regulated.md")
DAY13_REPORT = Path("docs/day-13-ultra-upgrade-report.md")
DAY13_ARTIFACT = Path("docs/artifacts/day13-enterprise-use-case-sample.md")
DAY13_PACK_CI = Path("docs/artifacts/day13-enterprise-pack/enterprise-day13-ci.yml")
DAY13_EVIDENCE = Path("docs/artifacts/day13-enterprise-pack/evidence/day13-execution-summary.json")

README_EXPECTED = [
    "## 🏢 Day 13 ultra: enterprise/regulated use-case page",
    "python -m sdetkit enterprise-use-case --format text --strict",
    "python -m sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict",
    "python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
    "python scripts/check_day13_enterprise_use_case_contract.py",
    "docs/day-13-ultra-upgrade-report.md",
]

DOCS_INDEX_EXPECTED = [
    "## Day 13 ultra upgrades (enterprise/regulated use-case page)",
    "enterprise + regulated workflow",
    "sdetkit enterprise-use-case --format text --strict",
    "sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict",
    "sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
    "artifacts/day13-enterprise-use-case-sample.md",
]

DOCS_CLI_EXPECTED = [
    "## enterprise-use-case",
    "sdetkit enterprise-use-case --format markdown --output docs/artifacts/day13-enterprise-use-case-sample.md",
    "sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict",
    "sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
    "--write-defaults",
    "--evidence-dir",
]

USE_CASE_EXPECTED = [
    "# Enterprise + regulated workflow",
    "## 15-minute enterprise baseline",
    "python -m sdetkit repo audit . --profile enterprise --format json",
    "python -m pytest -q tests/test_enterprise_use_case.py tests/test_cli_help_lists_subcommands.py",
    "## Automated evidence bundle",
    "name: enterprise-compliance-lane",
    "## Rollout model across business units",
]

REPORT_EXPECTED = [
    "Day 13 big upgrade",
    "python -m sdetkit enterprise-use-case --format json --strict",
    "python -m sdetkit enterprise-use-case --write-defaults --format json --strict",
    "python -m sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict",
    "python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
    "scripts/check_day13_enterprise_use_case_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Day 13 enterprise use-case page",
    "- Score: **100.0** (15/15)",
    "sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict",
    "sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
]

PACK_CI_EXPECTED = [
    "name: enterprise-compliance-lane",
    "python -m sdetkit enterprise-use-case --format json --strict",
    "python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
]

EVIDENCE_EXPECTED = [
    '"name": "day13-enterprise-execution"',
    '"total_commands": 5',
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
        USE_CASE_PAGE,
        DAY13_REPORT,
        DAY13_ARTIFACT,
        DAY13_PACK_CI,
        DAY13_EVIDENCE,
    ]
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
            f'{USE_CASE_PAGE}: missing "{m}"' for m in _missing(USE_CASE_PAGE, USE_CASE_EXPECTED)
        )
        errors.extend(
            f'{DAY13_REPORT}: missing "{m}"' for m in _missing(DAY13_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{DAY13_ARTIFACT}: missing "{m}"' for m in _missing(DAY13_ARTIFACT, ARTIFACT_EXPECTED)
        )
        errors.extend(
            f'{DAY13_PACK_CI}: missing "{m}"' for m in _missing(DAY13_PACK_CI, PACK_CI_EXPECTED)
        )
        errors.extend(
            f'{DAY13_EVIDENCE}: missing "{m}"' for m in _missing(DAY13_EVIDENCE, EVIDENCE_EXPECTED)
        )

    if errors:
        print("day13-enterprise-use-case-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day13-enterprise-use-case-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
