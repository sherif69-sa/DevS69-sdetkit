#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
LANE_REPORT = Path("docs/impact-6-ultra-upgrade-report.md")
LANE_ARTIFACT = Path("docs/artifacts/conversion-qa-sample-6.md")
DOCS_QA_MODULE = Path("src/sdetkit/docs_qa.py")

REQUIRED_README_SNIPPETS = [
    "## 🔗 Day 6 ultra: conversion QA hardening",
    "python -m sdetkit docs-qa --format text",
    "python -m sdetkit docs-qa --format markdown --output docs/artifacts/conversion-qa-sample-6.md",
    "docs/impact-6-ultra-upgrade-report.md",
]

REQUIRED_INDEX_SNIPPETS = [
    "Day 6 ultra upgrade report",
    "sdetkit docs-qa --format text",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 6 big upgrade",
    "src/sdetkit/docs_qa.py",
    "tests/test_docs_qa.py",
    "python scripts/check_conversion_contract_6.py",
]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    readme = _read(README)
    docs_index = _read(DOCS_INDEX)
    report = _read(LANE_REPORT)

    for s in REQUIRED_README_SNIPPETS:
        if s not in readme:
            errors.append(f"missing README snippet: {s}")

    for s in REQUIRED_INDEX_SNIPPETS:
        if s not in docs_index:
            errors.append(f"missing docs/index snippet: {s}")

    for s in REQUIRED_REPORT_SNIPPETS:
        if s not in report:
            errors.append(f"missing Day 6 report snippet: {s}")

    for p in [LANE_REPORT, LANE_ARTIFACT, DOCS_QA_MODULE]:
        if not p.exists():
            errors.append(f"missing required file: {p}")

    if errors:
        print("conversion-contract check failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1

    print("conversion-contract check passed")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
