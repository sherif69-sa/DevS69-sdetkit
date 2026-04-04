from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
USE_CASE_PAGE = Path("docs/use-cases-enterprise-regulated.md")
LANE_REPORT = Path("docs/enterprise-readiness-report.md")
LANE_ARTIFACT = Path("docs/artifacts/enterprise-readiness-sample.md")
ENTERPRISE_PACK_CI = Path("docs/artifacts/enterprise-readiness-pack/enterprise-readiness-ci.yml")
ENTERPRISE_EVIDENCE = Path(
    "docs/artifacts/enterprise-readiness-pack/evidence/enterprise-readiness-execution-summary.json"
)

README_EXPECTED = [
    "## Enterprise readiness",
    "python -m sdetkit enterprise-readiness --format text --strict",
    "python -m sdetkit enterprise-readiness --emit-pack-dir docs/artifacts/enterprise-readiness-pack --format json --strict",
    "python -m sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict",
    "python scripts/check_enterprise_readiness_contract.py",
    "docs/enterprise-readiness-report.md",
]

DOCS_INDEX_EXPECTED = [
    "## Enterprise readiness",
    "enterprise + regulated workflow",
    "sdetkit enterprise-readiness --format text --strict",
    "sdetkit enterprise-readiness --emit-pack-dir docs/artifacts/enterprise-readiness-pack --format json --strict",
    "sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict",
    "artifacts/enterprise-readiness-sample.md",
]

DOCS_CLI_EXPECTED = [
    "## enterprise-readiness",
    "sdetkit enterprise-readiness --format markdown --output docs/artifacts/enterprise-readiness-sample.md",
    "sdetkit enterprise-readiness --emit-pack-dir docs/artifacts/enterprise-readiness-pack --format json --strict",
    "sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict",
    "--write-defaults",
    "--evidence-dir",
]

USE_CASE_EXPECTED = [
    "# Enterprise + regulated workflow",
    "## 15-minute enterprise baseline",
    "python -m sdetkit repo audit . --profile enterprise --format json",
    "python -m pytest -q tests/test_enterprise_readiness.py tests/test_cli_help_lists_subcommands.py",
    "## Automated evidence bundle",
    "name: enterprise-compliance-lane",
    "## Rollout model across business units",
]

REPORT_EXPECTED = [
    "Enterprise readiness",
    "python -m sdetkit enterprise-readiness --format json --strict",
    "python -m sdetkit enterprise-readiness --write-defaults --format json --strict",
    "python -m sdetkit enterprise-readiness --emit-pack-dir docs/artifacts/enterprise-readiness-pack --format json --strict",
    "python -m sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict",
    "scripts/check_enterprise_readiness_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Enterprise readiness",
    "- Score: **100.0** (15/15)",
    "sdetkit enterprise-readiness --emit-pack-dir docs/artifacts/enterprise-readiness-pack --format json --strict",
    "sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict",
]

PACK_CI_EXPECTED = [
    "name: enterprise-compliance-lane",
    "python -m sdetkit enterprise-readiness --format json --strict",
    "python -m sdetkit enterprise-readiness --execute --evidence-dir docs/artifacts/enterprise-readiness-pack/evidence --format json --strict",
]

EVIDENCE_EXPECTED = [
    '"name": "enterprise-readiness-execution"',
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
        LANE_REPORT,
        LANE_ARTIFACT,
        ENTERPRISE_PACK_CI,
        ENTERPRISE_EVIDENCE,
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
            f'{LANE_REPORT}: missing "{m}"' for m in _missing(LANE_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{LANE_ARTIFACT}: missing "{m}"' for m in _missing(LANE_ARTIFACT, ARTIFACT_EXPECTED)
        )
        errors.extend(
            f'{ENTERPRISE_PACK_CI}: missing "{m}"'
            for m in _missing(ENTERPRISE_PACK_CI, PACK_CI_EXPECTED)
        )
        errors.extend(
            f'{ENTERPRISE_EVIDENCE}: missing "{m}"'
            for m in _missing(ENTERPRISE_EVIDENCE, EVIDENCE_EXPECTED)
        )

    if errors:
        print("enterprise-readiness-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("enterprise-readiness-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
