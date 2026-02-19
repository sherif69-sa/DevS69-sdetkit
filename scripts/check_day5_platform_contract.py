#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

README = Path("README.md")
DAY5_REPORT = Path("docs/day-5-ultra-upgrade-report.md")
DAY5_ARTIFACT = Path("docs/artifacts/day5-platform-onboarding-sample.md")

REQUIRED_README_SNIPPETS = [
    "## 🖥️ Day 5 ultra: platform onboarding boost",
    "python -m sdetkit onboarding --format text --platform all",
    "python -m sdetkit onboarding --format markdown --platform all --output docs/artifacts/day5-platform-onboarding-sample.md",
    "docs/day-5-ultra-upgrade-report.md",
]

REQUIRED_DAY5_SECTION_LINKS = [
    "docs/day-5-ultra-upgrade-report.md",
    "docs/artifacts/day5-platform-onboarding-sample.md",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 5 big boost",
    "src/sdetkit/onboarding.py",
    "tests/test_onboarding_cli.py",
    "python -m sdetkit onboarding --format markdown --platform all --output docs/artifacts/day5-platform-onboarding-sample.md",
]


def _day5_section(text: str) -> str:
    start = text.find("## 🖥️ Day 5 ultra: platform onboarding boost")
    if start == -1:
        return ""
    remainder = text[start:]
    match = re.search(r"\n## ", remainder[1:])
    if not match:
        return remainder
    return remainder[: match.start() + 1]


def main() -> int:
    errors: list[str] = []

    if not README.exists():
        print("README.md missing", file=sys.stderr)
        return 2

    readme_text = README.read_text(encoding="utf-8")
    day5_section = _day5_section(readme_text)

    for snippet in REQUIRED_README_SNIPPETS:
        if snippet not in readme_text:
            errors.append(f"missing README snippet: {snippet}")

    if not day5_section:
        errors.append("missing Day 5 ultra section in README")

    for link in REQUIRED_DAY5_SECTION_LINKS:
        if link not in day5_section:
            errors.append(f"missing Day 5 section link: {link}")
        if not Path(link).exists():
            errors.append(f"missing link target: {link}")

    if not DAY5_REPORT.exists():
        errors.append("missing docs/day-5-ultra-upgrade-report.md")
    else:
        report_text = DAY5_REPORT.read_text(encoding="utf-8")
        for snippet in REQUIRED_REPORT_SNIPPETS:
            if snippet not in report_text:
                errors.append(f"missing Day 5 report snippet: {snippet}")

    if not DAY5_ARTIFACT.exists():
        errors.append("missing docs/artifacts/day5-platform-onboarding-sample.md")

    if errors:
        print("day5-platform-contract check failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("day5-platform-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
