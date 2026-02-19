#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

README = Path("README.md")
DAY4_REPORT = Path("docs/day-4-ultra-upgrade-report.md")
DAY4_ARTIFACT = Path("docs/artifacts/day4-skills-sample.md")

REQUIRED_README_SNIPPETS = [
    "## 🧠 Day 4 ultra: skills expansion",
    "python -m sdetkit agent templates list",
    "python -m sdetkit agent templates run-all --output-dir .sdetkit/agent/template-runs",
    "docs/day-4-ultra-upgrade-report.md",
]

REQUIRED_DAY4_SECTION_LINKS = [
    "docs/day-4-ultra-upgrade-report.md",
    "docs/artifacts/day4-skills-sample.md",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 4 scale-up",
    "src/sdetkit/agent/cli.py",
    "tests/test_agent_templates_cli.py",
    "python scripts/check_day4_skills_contract.py",
]


def _day4_section(text: str) -> str:
    start = text.find("## 🧠 Day 4 ultra: skills expansion")
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
    day4_section = _day4_section(readme_text)

    for snippet in REQUIRED_README_SNIPPETS:
        if snippet not in readme_text:
            errors.append(f"missing README snippet: {snippet}")

    if not day4_section:
        errors.append("missing Day 4 ultra section in README")

    for link in REQUIRED_DAY4_SECTION_LINKS:
        if link not in day4_section:
            errors.append(f"missing Day 4 section link: {link}")
        if not Path(link).exists():
            errors.append(f"missing link target: {link}")

    if not DAY4_REPORT.exists():
        errors.append("missing docs/day-4-ultra-upgrade-report.md")
    else:
        report_text = DAY4_REPORT.read_text(encoding="utf-8")
        for snippet in REQUIRED_REPORT_SNIPPETS:
            if snippet not in report_text:
                errors.append(f"missing Day 4 report snippet: {snippet}")

    if not DAY4_ARTIFACT.exists():
        errors.append("missing docs/artifacts/day4-skills-sample.md")

    if errors:
        print("day4-skills-contract check failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("day4-skills-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
