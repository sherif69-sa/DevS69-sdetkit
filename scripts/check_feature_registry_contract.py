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
        prog="check_feature_registry_contract.py",
        description="Validate feature registry entries and linked repo assets.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used to validate linked docs/tests paths.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    _bootstrap_import_path(repo_root)

    from sdetkit.feature_registry import validate_feature_registry_contract

    errors = validate_feature_registry_contract(repo_root)
    if errors:
        for item in errors:
            print(f"feature-registry-contract: {item}", file=sys.stderr)
        return 1

    print("feature-registry-contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
