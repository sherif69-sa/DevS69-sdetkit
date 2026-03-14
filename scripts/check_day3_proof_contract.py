#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

README = Path("README.md")
DAY3_REPORT = Path("docs/impact-3-ultra-upgrade-report.md")
DAY3_ARTIFACT = Path("docs/artifacts/day3-proof-sample.md")

REQUIRED_README_SNIPPETS = [
    "## 📸 Day 3 ultra: proof pack",
    "python -m sdetkit proof --execute --strict --format text",
    "python -m sdetkit proof --execute --strict --format markdown --output docs/artifacts/day3-proof-sample.md",
    "docs/impact-3-ultra-upgrade-report.md",
]

REQUIRED_DAY3_SECTION_LINKS = [
    "docs/impact-3-ultra-upgrade-report.md",
    "docs/artifacts/day3-proof-sample.md",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 3 big boost",
    "src/sdetkit/proof.py",
    "tests/test_proof_cli.py",
    "python -m sdetkit proof --execute --strict --format markdown --output docs/artifacts/day3-proof-sample.md",
]


def _day3_section(text: str) -> str:
    start = text.find("## 📸 Day 3 ultra: proof pack")
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
    day3_section = _day3_section(readme_text)

    for snippet in REQUIRED_README_SNIPPETS:
        if snippet not in readme_text:
            errors.append(f"missing README snippet: {snippet}")

    if not day3_section:
        errors.append("missing Day 3 ultra section in README")

    for link in REQUIRED_DAY3_SECTION_LINKS:
        if link not in day3_section:
            errors.append(f"missing Day 3 section link: {link}")
        if not Path(link).exists():
            errors.append(f"missing link target: {link}")

    if not DAY3_REPORT.exists():
        errors.append("missing docs/impact-3-ultra-upgrade-report.md")
    else:
        report_text = DAY3_REPORT.read_text(encoding="utf-8")
        for snippet in REQUIRED_REPORT_SNIPPETS:
            if snippet not in report_text:
                errors.append(f"missing Day 3 report snippet: {snippet}")

    if not DAY3_ARTIFACT.exists():
        errors.append("missing docs/artifacts/day3-proof-sample.md")

    if errors:
        print("day3-proof-contract check failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("day3-proof-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
