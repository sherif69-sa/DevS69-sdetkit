from __future__ import annotations

import sys
from pathlib import Path

PAGE = Path("docs/integrations-gitlab-ci-quickstart.md")
ARTIFACT = Path("docs/artifacts/gitlab-ci-onboarding-sample.md")
PACK_STRICT = Path("docs/artifacts/gitlab-ci-onboarding-pack/gitlab-ci-sdetkit-strict.yml")
PACK_NIGHTLY = Path("docs/artifacts/gitlab-ci-onboarding-pack/gitlab-ci-sdetkit-nightly.yml")
EVIDENCE = Path(
    "docs/artifacts/gitlab-ci-onboarding-pack/evidence/gitlab-ci-onboarding-execution-summary.json"
)

EXPECTED = {
    PAGE: [
        "# GitLab CI quickstart",
        "python scripts/check_gitlab_ci_onboarding_contract.py",
        "docs/artifacts/gitlab-ci-onboarding-pack/evidence",
    ],
    ARTIFACT: [
        "# GitLab CI quickstart",
        "docs/artifacts/gitlab-ci-onboarding-pack",
    ],
    PACK_STRICT: [
        "strict-gate:",
        "python -m sdetkit gitlab-ci-onboarding --format json --strict",
    ],
    PACK_NIGHTLY: [
        "nightly-audit:",
        "python -m sdetkit gitlab-ci-onboarding --execute --evidence-dir docs/artifacts/gitlab-ci-onboarding-pack/evidence --format json --strict",
    ],
    EVIDENCE: [
        '"name": "gitlab-ci-onboarding-execution"',
        '"total_commands": 4',
    ],
}


def _missing(path: Path, expected: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [item for item in expected if item not in text]


def main() -> int:
    errors: list[str] = []
    for path, expected in EXPECTED.items():
        if not path.exists():
            errors.append(f"missing required file: {path}")
            continue
        errors.extend(f'{path}: missing "{m}"' for m in _missing(path, expected))

    if errors:
        print("gitlab-ci-onboarding contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("gitlab-ci-onboarding contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
