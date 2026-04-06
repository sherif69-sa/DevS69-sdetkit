#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

ANCHOR_PATTERN = re.compile(r"anchor([0-9]{1,2})")
TEST_NAME_PATTERN = re.compile(r"(def test_[^(]*?)_without_anchor\d{1,2}(\(tmp_path: Path\) -> None:)")
PLAN_ID_PATTERN = re.compile(r'("plan_id"\s*:\s*")anchor[0-9]{1,2}-([^"\\n]+")')


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for top in ("src", "tests", "docs", "scripts"):
        base = root / top
        if not base.exists():
            continue
        files.extend(p for p in base.rglob("*") if p.is_file())
    return files


def build_inventory(root: Path) -> dict[str, dict[str, set[str]]]:
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for p in _iter_files(root):
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8", errors="ignore")
        anchors = set(ANCHOR_PATTERN.findall(text))
        if not anchors:
            continue
        if rel.startswith("docs/artifacts/"):
            bucket = "artifacts"
        elif rel.startswith("docs/roadmap/"):
            bucket = "roadmap"
        elif rel.startswith("src/"):
            bucket = "active-src"
        elif rel.startswith("tests/"):
            bucket = "active-tests"
        elif rel.startswith("scripts/"):
            bucket = "active-scripts"
        else:
            bucket = "other"
        for anchor in anchors:
            grouped[bucket][anchor].add(rel)
    return grouped


def rewrite_tests(root: Path) -> tuple[int, int]:
    renamed_tests = 0
    rewritten_plan_ids = 0
    for p in (root / "tests").glob("test_*.py"):
        text = p.read_text(encoding="utf-8")
        new_text, n1 = TEST_NAME_PATTERN.subn(r"\1_without_prereq_baseline\2", text)
        new_text, n2 = PLAN_ID_PATTERN.subn(r"\1\2", new_text)
        if n1 or n2:
            p.write_text(new_text, encoding="utf-8")
            renamed_tests += n1
            rewritten_plan_ids += n2
    return renamed_tests, rewritten_plan_ids


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventory and optional cleanup for anchorNN legacy naming")
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--fix-tests", action="store_true", help="rewrite test names and test fixture plan_ids")
    ns = ap.parse_args()

    root = Path(ns.root).resolve()
    inv = build_inventory(root)
    print("Inventory:")
    for bucket in sorted(inv):
        print(f"[{bucket}]")
        for anchor in sorted(inv[bucket], key=lambda d: int(d)):
            print(f"  anchor{anchor}: {len(inv[bucket][anchor])} files")

    if ns.fix_tests:
        renamed_tests, rewritten_plan_ids = rewrite_tests(root)
        print(f"\nApplied fixes: renamed_tests={renamed_tests}, rewritten_plan_ids={rewritten_plan_ids}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
