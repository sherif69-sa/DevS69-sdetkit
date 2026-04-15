#!/usr/bin/env python3
"""Promote generated top-tier bundle outputs to canonical docs/artifacts sample paths."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _copy(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"missing source artifact: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote top-tier bundle outputs")
    ap.add_argument("--bundle-dir", required=True)
    ap.add_argument("--date-tag", required=True, help="Date tag like 2026-04-17")
    args = ap.parse_args()

    bundle = Path(args.bundle_dir)
    date = args.date_tag

    mappings = {
        bundle / "portfolio-scorecard.json": Path(f"docs/artifacts/portfolio-scorecard-sample-{date}.json"),
        bundle / "kpi-weekly.json": Path(f"docs/artifacts/kpi-weekly-from-portfolio-{date}.json"),
        bundle / "kpi-contract-check.json": Path(f"docs/artifacts/kpi-weekly-contract-check-{date}.json"),
        bundle / "top-tier-contract-check.json": Path(f"docs/artifacts/top-tier-contract-check-{date}.json"),
    }

    for src, dst in mappings.items():
        _copy(src, dst)

    print(f"promoted {len(mappings)} artifacts for {date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
