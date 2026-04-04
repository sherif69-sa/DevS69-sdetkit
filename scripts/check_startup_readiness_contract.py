from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
USE_CASE_PAGE = Path("docs/use-cases-startup-small-team.md")
LANE_REPORT = Path("docs/startup-readiness-report.md")
LANE_ARTIFACT = Path("docs/artifacts/startup-readiness-sample.md")
STARTUP_PACK_CI = Path("docs/artifacts/startup-readiness-pack/startup-readiness-ci.yml")

README_EXPECTED = [
    "## Startup readiness",
    "python -m sdetkit startup-readiness --format text --strict",
    "python -m sdetkit startup-readiness --emit-pack-dir docs/artifacts/startup-readiness-pack --format json --strict",
    "python scripts/check_startup_readiness_contract.py",
    "docs/startup-readiness-report.md",
]

DOCS_INDEX_EXPECTED = [
    "## Startup readiness",
    "startup + small-team workflow",
    "sdetkit startup-readiness --format text --strict",
    "sdetkit startup-readiness --emit-pack-dir docs/artifacts/startup-readiness-pack --format json --strict",
    "artifacts/startup-readiness-sample.md",
]

DOCS_CLI_EXPECTED = [
    "## startup-readiness",
    "sdetkit startup-readiness --format markdown --output docs/artifacts/startup-readiness-sample.md",
    "sdetkit startup-readiness --emit-pack-dir docs/artifacts/startup-readiness-pack --format json --strict",
    "--write-defaults",
]

USE_CASE_EXPECTED = [
    "# Startup + small-team workflow",
    "## 10-minute startup path",
    "python -m sdetkit doctor --format text",
    "python -m pytest -q tests/test_startup_readiness.py tests/test_cli_help_lists_subcommands.py",
    "## CI fast-lane recipe",
    "name: startup-quality-fast-lane",
    "## Exit criteria to graduate to enterprise workflow",
]

REPORT_EXPECTED = [
    "Startup readiness",
    "python -m sdetkit startup-readiness --format json --strict",
    "python -m sdetkit startup-readiness --write-defaults --format json --strict",
    "python -m sdetkit startup-readiness --emit-pack-dir docs/artifacts/startup-readiness-pack --format json --strict",
    "scripts/check_startup_readiness_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Startup readiness",
    "- Score: **100.0** (14/14)",
    "sdetkit startup-readiness --emit-pack-dir docs/artifacts/startup-readiness-pack --format json --strict",
]

PACK_CI_EXPECTED = [
    "name: startup-quality-fast-lane",
    "python -m sdetkit startup-readiness --format json --strict",
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
        STARTUP_PACK_CI,
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
            f'{STARTUP_PACK_CI}: missing "{m}"' for m in _missing(STARTUP_PACK_CI, PACK_CI_EXPECTED)
        )

    if errors:
        print("startup-readiness-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("startup-readiness-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
