#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DAY6_REPORT = Path("docs/day-6-ultra-upgrade-report.md")
DAY6_ARTIFACT = Path("docs/artifacts/day6-conversion-qa-sample.md")
DOCS_QA_MODULE = Path("src/sdetkit/docs_qa.py")

REQUIRED_README_SNIPPETS = [
    "## 🔗 Day 6 ultra: conversion QA hardening",
    "python -m sdetkit docs-qa --format text",
    "python -m sdetkit docs-qa --format markdown --output docs/artifacts/day6-conversion-qa-sample.md",
    "docs/day-6-ultra-upgrade-report.md",
]

REQUIRED_INDEX_SNIPPETS = [
    "Day 6 ultra upgrade report",
    "sdetkit docs-qa --format text",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 6 big upgrade",
    "src/sdetkit/docs_qa.py",
    "tests/test_docs_qa.py",
    "python scripts/check_day6_conversion_contract.py",
]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    readme = _read(README)
    docs_index = _read(DOCS_INDEX)
    report = _read(DAY6_REPORT)

    for s in REQUIRED_README_SNIPPETS:
        if s not in readme:
            errors.append(f"missing README snippet: {s}")

    for s in REQUIRED_INDEX_SNIPPETS:
        if s not in docs_index:
            errors.append(f"missing docs/index snippet: {s}")

    for s in REQUIRED_REPORT_SNIPPETS:
        if s not in report:
            errors.append(f"missing Day 6 report snippet: {s}")

    for p in [DAY6_REPORT, DAY6_ARTIFACT, DOCS_QA_MODULE]:
        if not p.exists():
            errors.append(f"missing required file: {p}")

    if errors:
        print("day6-conversion-contract check failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1

    print("day6-conversion-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
