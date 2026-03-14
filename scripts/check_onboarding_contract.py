#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ARTIFACT = Path("docs/artifacts/day1-onboarding-sample.md")
REPORT = Path("docs/impact-1-ultra-upgrade-report.md")

REQUIRED_ARTIFACT_SNIPPETS = [
    "| Role | First command | Next action |",
    "SDET / QA engineer",
    "Platform / DevOps engineer",
    "Security / compliance lead",
    "Engineering manager / tech lead",
    "Quick start:",
]

REQUIRED_REPORT_SNIPPETS = [
    "`src/sdetkit/onboarding.py`",
    "`tests/test_onboarding_cli.py`",
    "`scripts/check_onboarding_contract.py`",
    "`docs/artifacts/day1-onboarding-sample.md`",
    "`python -m sdetkit onboarding --format markdown --output docs/artifacts/day1-onboarding-sample.md`",
    "`python scripts/check_onboarding_contract.py`",
]

REQUIRED_DOC_PATHS = [
    "docs/doctor.md",
    "docs/repo-audit.md",
    "docs/github-action.md",
    "docs/security.md",
    "docs/policy-and-baselines.md",
    "docs/automation-os.md",
    "docs/repo-tour.md",
]


def main() -> int:
    errors: list[str] = []

    if not ARTIFACT.exists():
        errors.append(f"missing artifact: {ARTIFACT}")
        artifact_text = ""
    else:
        artifact_text = ARTIFACT.read_text(encoding="utf-8")

    if not REPORT.exists():
        errors.append(f"missing report: {REPORT}")
        report_text = ""
    else:
        report_text = REPORT.read_text(encoding="utf-8")

    for snippet in REQUIRED_ARTIFACT_SNIPPETS:
        if snippet not in artifact_text:
            errors.append(f"missing artifact snippet: {snippet}")

    for snippet in REQUIRED_REPORT_SNIPPETS:
        if snippet not in report_text:
            errors.append(f"missing report snippet: {snippet}")

    for rel_path in REQUIRED_DOC_PATHS:
        if not Path(rel_path).exists():
            errors.append(f"missing docs link target: {rel_path}")

    if errors:
        print("onboarding-contract check failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("onboarding-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
