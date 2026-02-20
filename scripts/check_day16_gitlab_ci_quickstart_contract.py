from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_CLI = Path("docs/cli.md")
QUICKSTART_PAGE = Path("docs/integrations-gitlab-ci-quickstart.md")
DAY16_REPORT = Path("docs/day-16-ultra-upgrade-report.md")
DAY16_ARTIFACT = Path("docs/artifacts/day16-gitlab-ci-quickstart-sample.md")
DAY16_PACK_STRICT = Path("docs/artifacts/day16-gitlab-pack/day16-sdetkit-strict.yml")
DAY16_PACK_NIGHTLY = Path("docs/artifacts/day16-gitlab-pack/day16-sdetkit-nightly.yml")
DAY16_EVIDENCE = Path("docs/artifacts/day16-gitlab-pack/evidence/day16-execution-summary.json")

README_EXPECTED = [
    "## 🦊 Day 16 ultra: GitLab CI quickstart",
    "python -m sdetkit gitlab-ci-quickstart --format text --strict",
    "python -m sdetkit gitlab-ci-quickstart --format json --variant strict --strict",
    "python -m sdetkit gitlab-ci-quickstart --emit-pack-dir docs/artifacts/day16-gitlab-pack --format json --strict",
    "python -m sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict",
    "python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
    "python scripts/check_day16_gitlab_ci_quickstart_contract.py",
    "docs/day-16-ultra-upgrade-report.md",
]

DOCS_INDEX_EXPECTED = [
    "## Day 16 ultra upgrades (GitLab CI quickstart)",
    "sdetkit gitlab-ci-quickstart --format text --strict",
    "sdetkit gitlab-ci-quickstart --format json --variant strict --strict",
    "sdetkit gitlab-ci-quickstart --emit-pack-dir docs/artifacts/day16-gitlab-pack --format json --strict",
    "sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict",
    "sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
    "artifacts/day16-gitlab-ci-quickstart-sample.md",
]

DOCS_CLI_EXPECTED = [
    "## gitlab-ci-quickstart",
    "sdetkit gitlab-ci-quickstart --format markdown --variant strict --output docs/artifacts/day16-gitlab-ci-quickstart-sample.md",
    "sdetkit gitlab-ci-quickstart --emit-pack-dir docs/artifacts/day16-gitlab-pack --format json --strict",
    "sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict",
    "sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
    "--write-defaults",
    "--variant",
    "--bootstrap-pipeline",
    "--pipeline-path",
    "--evidence-dir",
]

QUICKSTART_EXPECTED = [
    "# GitLab CI quickstart (Day 16)",
    "## Strict pipeline variant",
    "## Nightly reliability variant",
    "## Multi-channel distribution loop",
    "## Failure recovery playbook",
    "quickstart-gate:",
    "strict-gate:",
    "nightly-audit:",
    "python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
]

REPORT_EXPECTED = [
    "Day 16 big upgrade",
    "python -m sdetkit gitlab-ci-quickstart --format json --variant strict --strict",
    "python -m sdetkit gitlab-ci-quickstart --emit-pack-dir docs/artifacts/day16-gitlab-pack --format json --strict",
    "python -m sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict",
    "python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
    "scripts/check_day16_gitlab_ci_quickstart_contract.py",
]

ARTIFACT_EXPECTED = [
    "# Day 16 GitLab CI quickstart",
    "- Variant: `strict`",
    "- Score: **100.0** (19/19)",
    "sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
]

PACK_STRICT_EXPECTED = [
    "strict-gate:",
    "python -m sdetkit gitlab-ci-quickstart --format json --strict",
]

PACK_NIGHTLY_EXPECTED = [
    "nightly-audit:",
    "python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
]

EVIDENCE_EXPECTED = [
    '"name": "day16-gitlab-ci-execution"',
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
        DAY16_REPORT,
        DAY16_ARTIFACT,
        DAY16_PACK_STRICT,
        DAY16_PACK_NIGHTLY,
        DAY16_EVIDENCE,
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
            f'{DAY16_REPORT}: missing "{m}"' for m in _missing(DAY16_REPORT, REPORT_EXPECTED)
        )
        errors.extend(
            f'{DAY16_ARTIFACT}: missing "{m}"' for m in _missing(DAY16_ARTIFACT, ARTIFACT_EXPECTED)
        )
        errors.extend(
            f'{DAY16_PACK_STRICT}: missing "{m}"'
            for m in _missing(DAY16_PACK_STRICT, PACK_STRICT_EXPECTED)
        )
        errors.extend(
            f'{DAY16_PACK_NIGHTLY}: missing "{m}"'
            for m in _missing(DAY16_PACK_NIGHTLY, PACK_NIGHTLY_EXPECTED)
        )
        errors.extend(
            f'{DAY16_EVIDENCE}: missing "{m}"' for m in _missing(DAY16_EVIDENCE, EVIDENCE_EXPECTED)
        )

    if errors:
        print("day16-gitlab-ci-quickstart-contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("day16-gitlab-ci-quickstart-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
