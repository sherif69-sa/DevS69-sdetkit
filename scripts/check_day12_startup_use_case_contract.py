from __future__ import annotations

from pathlib import Path
import sys

README = Path('README.md')
DOCS_INDEX = Path('docs/index.md')
DOCS_CLI = Path('docs/cli.md')
USE_CASE_PAGE = Path('docs/use-cases-startup-small-team.md')
DAY12_REPORT = Path('docs/day-12-ultra-upgrade-report.md')
DAY12_ARTIFACT = Path('docs/artifacts/day12-startup-use-case-sample.md')
DAY12_PACK_CI = Path('docs/artifacts/day12-startup-pack/startup-day12-ci.yml')

README_EXPECTED = [
    '## 🚀 Day 12 ultra: startup/small-team use-case page',
    'python -m sdetkit startup-use-case --format text --strict',
    'python -m sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict',
    'python scripts/check_day12_startup_use_case_contract.py',
    'docs/day-12-ultra-upgrade-report.md',
]

DOCS_INDEX_EXPECTED = [
    '## Day 12 ultra upgrades (startup/small-team use-case page)',
    'startup + small-team workflow',
    'sdetkit startup-use-case --format text --strict',
    'sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict',
    'artifacts/day12-startup-use-case-sample.md',
]

DOCS_CLI_EXPECTED = [
    '## startup-use-case',
    'sdetkit startup-use-case --format markdown --output docs/artifacts/day12-startup-use-case-sample.md',
    'sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict',
    '--write-defaults',
]

USE_CASE_EXPECTED = [
    '# Startup + small-team workflow',
    '## 10-minute startup path',
    'python -m sdetkit doctor --format text',
    'python -m pytest -q tests/test_startup_use_case.py tests/test_cli_help_lists_subcommands.py',
    '## CI fast-lane recipe',
    'name: startup-quality-fast-lane',
    '## Exit criteria to graduate to enterprise workflow',
]

REPORT_EXPECTED = [
    'Day 12 big upgrade',
    'python -m sdetkit startup-use-case --format json --strict',
    'python -m sdetkit startup-use-case --write-defaults --format json --strict',
    'python -m sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict',
    'scripts/check_day12_startup_use_case_contract.py',
]

ARTIFACT_EXPECTED = [
    '# Day 12 startup use-case page',
    '- Score: **100.0** (14/14)',
    'sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict',
]

PACK_CI_EXPECTED = [
    'name: startup-quality-fast-lane',
    'python -m sdetkit startup-use-case --format json --strict',
]


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    return [item for item in expected if item not in text]


def main() -> int:
    errors: list[str] = []
    required = [README, DOCS_INDEX, DOCS_CLI, USE_CASE_PAGE, DAY12_REPORT, DAY12_ARTIFACT, DAY12_PACK_CI]
    for path in required:
        if not path.exists():
            errors.append(f'missing required file: {path}')

    if not errors:
        errors.extend(f'{README}: missing "{m}"' for m in _missing(README, README_EXPECTED))
        errors.extend(f'{DOCS_INDEX}: missing "{m}"' for m in _missing(DOCS_INDEX, DOCS_INDEX_EXPECTED))
        errors.extend(f'{DOCS_CLI}: missing "{m}"' for m in _missing(DOCS_CLI, DOCS_CLI_EXPECTED))
        errors.extend(f'{USE_CASE_PAGE}: missing "{m}"' for m in _missing(USE_CASE_PAGE, USE_CASE_EXPECTED))
        errors.extend(f'{DAY12_REPORT}: missing "{m}"' for m in _missing(DAY12_REPORT, REPORT_EXPECTED))
        errors.extend(f'{DAY12_ARTIFACT}: missing "{m}"' for m in _missing(DAY12_ARTIFACT, ARTIFACT_EXPECTED))
        errors.extend(f'{DAY12_PACK_CI}: missing "{m}"' for m in _missing(DAY12_PACK_CI, PACK_CI_EXPECTED))

    if errors:
        print('day12-startup-use-case-contract check failed:', file=sys.stderr)
        for error in errors:
            print(f' - {error}', file=sys.stderr)
        return 1

    print('day12-startup-use-case-contract check passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
