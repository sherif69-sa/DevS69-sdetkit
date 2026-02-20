from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
QUICKSTART_PAGE = Path("docs/integrations-github-actions-quickstart.md")
DAY15_REPORT = Path("docs/day-15-ultra-upgrade-report.md")
DAY15_ARTIFACT = Path("docs/artifacts/day15-github-actions-quickstart-sample.md")
DAY15_PACK_STRICT = Path("docs/artifacts/day15-github-pack/day15-sdetkit-strict.yml")
DAY15_PACK_NIGHTLY = Path("docs/artifacts/day15-github-pack/day15-sdetkit-nightly.yml")
DAY15_EVIDENCE = Path("docs/artifacts/day15-github-pack/evidence/day15-execution-summary.json")

README_EXPECTED = [
    "## 🔁 Day 15 ultra: GitHub Actions quickstart",
    "python -m sdetkit github-actions-quickstart --format text --strict",
    "python -m sdetkit github-actions-quickstart --format json --variant strict --strict",
    "python -m sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/day15-github-pack --format json --strict",
    "python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
    "python scripts/check_day15_github_actions_quickstart_contract.py",
    "docs/day-15-ultra-upgrade-report.md",
]

DOCS_INDEX_EXPECTED = [
    "## Day 15 ultra upgrades (GitHub Actions quickstart)",
    "sdetkit github-actions-quickstart --format text --strict",
    "sdetkit github-actions-quickstart --format json --variant strict --strict",
    "sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/day15-github-pack --format json --strict",
    "sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
    "artifacts/day15-github-actions-quickstart-sample.md",
]

DOCS_CLI_EXPECTED = [
    "## github-actions-quickstart",
    "sdetkit github-actions-quickstart --format markdown --variant strict --output docs/artifacts/day15-github-actions-quickstart-sample.md",
    "sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/day15-github-pack --format json --strict",
    "sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
    "--write-defaults",
    "--variant",
    "--evidence-dir",
]

QUICKSTART_EXPECTED = [
    "# GitHub Actions quickstart (Day 15)",
    "## Strict workflow variant",
    "## Nightly reliability variant",
    "## Multi-channel distribution loop",
    "## Failure recovery playbook",
    "name: sdetkit-github-quickstart",
    "name: sdetkit-github-strict",
    "name: sdetkit-github-nightly",
    "python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
]

REPORT_EXPECTED = [
    "Day 15 big upgrade",
    "python -m sdetkit github-actions-quickstart --format json --variant strict --strict",
    "python -m sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/day15-github-pack --format json --strict",
    "python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
    "scripts/check_day15_github_actions_quickstart_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Day 15 GitHub Actions quickstart",
    "- Variant: `strict`",
    "- Score: **100.0** (18/18)",
    "sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
]

PACK_STRICT_EXPECTED = [
    "name: sdetkit-github-strict",
    "python -m sdetkit github-actions-quickstart --format json --strict",
]

PACK_NIGHTLY_EXPECTED = [
    "name: sdetkit-github-nightly",
    "python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
]

EVIDENCE_EXPECTED = [
    '"name": "day15-github-actions-execution"',
    '"total_commands": 4',
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
        QUICKSTART_PAGE,
        DAY15_REPORT,
        DAY15_ARTIFACT,
        DAY15_PACK_STRICT,
        DAY15_PACK_NIGHTLY,
        DAY15_EVIDENCE,
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
            f'{QUICKSTART_PAGE}: missing "{m}"'
            for m in _missing(QUICKSTART_PAGE, QUICKSTART_EXPECTED)
        )
        errors.extend(
            f'{DAY15_REPORT}: missing "{m}"' for m in _missing(DAY15_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{DAY15_ARTIFACT}: missing "{m}"' for m in _missing(DAY15_ARTIFACT, ARTIFACT_EXPECTED)
        )
        errors.extend(
            f'{DAY15_PACK_STRICT}: missing "{m}"'
            for m in _missing(DAY15_PACK_STRICT, PACK_STRICT_EXPECTED)
        )
        errors.extend(
            f'{DAY15_PACK_NIGHTLY}: missing "{m}"'
            for m in _missing(DAY15_PACK_NIGHTLY, PACK_NIGHTLY_EXPECTED)
        )
        errors.extend(
            f'{DAY15_EVIDENCE}: missing "{m}"' for m in _missing(DAY15_EVIDENCE, EVIDENCE_EXPECTED)
        )

    if errors:
        print("day15-github-actions-quickstart-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day15-github-actions-quickstart-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
