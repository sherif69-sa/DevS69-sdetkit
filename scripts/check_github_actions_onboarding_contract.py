from __future__ import annotations

import sys
from pathlib import Path

PAGE = Path("docs/integrations-github-actions-quickstart.md")
ARTIFACT = Path("docs/artifacts/github-actions-onboarding-sample.md")
PACK_STRICT = Path(
    "docs/artifacts/github-actions-onboarding-pack/github-actions-sdetkit-strict.yml"
)
PACK_NIGHTLY = Path(
    "docs/artifacts/github-actions-onboarding-pack/github-actions-sdetkit-nightly.yml"
)
EVIDENCE = Path(
    "docs/artifacts/github-actions-onboarding-pack/evidence/github-actions-onboarding-execution-summary.json"
)

EXPECTED = {
    PAGE: [
        "# GitHub Actions quickstart",
        "python scripts/check_github_actions_onboarding_contract.py",
        "docs/artifacts/github-actions-onboarding-pack/evidence",
    ],
    ARTIFACT: [
        "# GitHub Actions quickstart",
        "docs/artifacts/github-actions-onboarding-pack",
    ],
    PACK_STRICT: [
        "name: sdetkit-github-strict",
        "python -m sdetkit github-actions-onboarding --format json --strict",
    ],
    PACK_NIGHTLY: [
        "name: sdetkit-github-nightly",
        "python -m sdetkit github-actions-onboarding --execute --evidence-dir docs/artifacts/github-actions-onboarding-pack/evidence --format json --strict",
    ],
    EVIDENCE: [
        '"name": "github-actions-onboarding-execution"',
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
        print("github-actions-onboarding contract check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("github-actions-onboarding contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
