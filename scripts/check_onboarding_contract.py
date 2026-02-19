#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

README = Path("README.md")
REQUIRED_SNIPPETS = [
    "## 🔥 Day 1 ultra upgrade pack",
    "sdetkit doctor --format markdown",
    "sdetkit repo audit --format markdown",
    "sdetkit security --format markdown",
    "docs/day-1-ultra-upgrade-report.md",
]
REQUIRED_DOC_PATHS = [
    "docs/repo-audit.md",
    "docs/github-action.md",
    "docs/security.md",
    "docs/policy-and-baselines.md",
    "docs/automation-os.md",
    "docs/day-1-ultra-upgrade-report.md",
]


def _day1_section(text: str) -> str:
    start = text.find("## 🔥 Day 1 ultra upgrade pack")
    if start == -1:
        return ""
    remainder = text[start:]
    m = re.search(r"\n## ", remainder[1:])
    if not m:
        return remainder
    return remainder[: m.start() + 1]


def main() -> int:
    if not README.exists():
        print("README.md missing", file=sys.stderr)
        return 2

    text = README.read_text(encoding="utf-8")
    section = _day1_section(text)
    errors: list[str] = []

    for snippet in REQUIRED_SNIPPETS:
        if snippet not in text:
            errors.append(f"missing snippet: {snippet}")

    if not section:
        errors.append("missing Day 1 ultra section")

    for rel_path in REQUIRED_DOC_PATHS:
        if rel_path not in section:
            errors.append(f"missing Day 1 link: {rel_path}")
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
