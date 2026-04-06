#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_import_path(repo_root: Path) -> None:
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync_feature_registry_docs.py",
        description="Sync docs/feature-registry.md table from src/sdetkit/data/feature_registry.json.",
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check-only mode. Exit non-zero if docs table is stale.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    _bootstrap_import_path(repo_root)

    from sdetkit.feature_registry import (
        _DOC_TABLE_END,
        _DOC_TABLE_START,
        load_feature_registry,
        render_feature_registry_docs_block,
    )

    docs_path = repo_root / "docs" / "feature-registry.md"
    if not docs_path.exists():
        print("missing docs/feature-registry.md", file=sys.stderr)
        return 1

    text = docs_path.read_text(encoding="utf-8")
    start = text.find(_DOC_TABLE_START)
    end = text.find(_DOC_TABLE_END)
    if start == -1 or end == -1 or end < start:
        print("docs markers missing; add feature-registry table markers", file=sys.stderr)
        return 1

    end += len(_DOC_TABLE_END)
    replacement = render_feature_registry_docs_block(load_feature_registry())
    updated = text[:start] + replacement + text[end:]

    if args.check:
        if updated != text:
            print("feature-registry docs table is stale", file=sys.stderr)
            return 1
        print("feature-registry docs table is up to date")
        return 0

    docs_path.write_text(updated, encoding="utf-8")
    print(f"updated {docs_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
