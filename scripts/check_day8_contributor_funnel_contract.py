#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DAY8_REPORT = Path("docs/day-8-ultra-upgrade-report.md")
DAY8_ARTIFACT = Path("docs/artifacts/day8-good-first-issues-sample.md")
DAY8_ISSUE_PACK = Path("docs/artifacts/day8-issue-pack")
DAY8_MODULE = Path("src/sdetkit/contributor_funnel.py")

REQUIRED_README_SNIPPETS = [
    "## 🧲 Day 8 ultra: contributor funnel backlog",
    "python -m sdetkit contributor-funnel --format text --strict",
    "python -m sdetkit contributor-funnel --area docs --issue-pack-dir docs/artifacts/day8-issue-pack",
    "docs/day-8-ultra-upgrade-report.md",
]

REQUIRED_INDEX_SNIPPETS = [
    "Day 8 ultra upgrade report",
    "sdetkit contributor-funnel --format text --strict",
    "sdetkit contributor-funnel --area docs --issue-pack-dir docs/artifacts/day8-issue-pack",
]

REQUIRED_REPORT_SNIPPETS = [
    "Day 8 big upgrade",
    "src/sdetkit/contributor_funnel.py",
    "tests/test_contributor_funnel.py",
    "python scripts/check_day8_contributor_funnel_contract.py",
]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    readme = _read(README)
    docs_index = _read(DOCS_INDEX)
    report = _read(DAY8_REPORT)

    for s in REQUIRED_README_SNIPPETS:
        if s not in readme:
            errors.append(f"missing README snippet: {s}")

    for s in REQUIRED_INDEX_SNIPPETS:
        if s not in docs_index:
            errors.append(f"missing docs/index snippet: {s}")

    for s in REQUIRED_REPORT_SNIPPETS:
        if s not in report:
            errors.append(f"missing Day 8 report snippet: {s}")

    for p in [DAY8_REPORT, DAY8_ARTIFACT, DAY8_MODULE]:
        if not p.exists():
            errors.append(f"missing required file: {p}")

    issue_pack_files = sorted(DAY8_ISSUE_PACK.glob("gfi-*.md")) if DAY8_ISSUE_PACK.exists() else []
    if len(issue_pack_files) < 5:
        errors.append("missing issue-pack artifacts: expected at least 5 gfi-*.md files")

    if errors:
        print("day8-contributor-funnel-contract check failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1

    print("day8-contributor-funnel-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
