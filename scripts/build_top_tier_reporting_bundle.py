#!/usr/bin/env python3
"""Build complete top-tier reporting bundle (portfolio + KPI + contract checks)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()



def main() -> int:
    ap = argparse.ArgumentParser(description="Build top-tier reporting bundle")
    ap.add_argument("--input", required=True, help="Normalized portfolio input file (JSON or JSONL)")
    ap.add_argument("--out-dir", required=True, help="Output directory for generated artifacts")
    ap.add_argument("--window-start", required=True)
    ap.add_argument("--window-end", required=True)
    ap.add_argument("--generated-at", default="")
    ap.add_argument("--schema-version", default="1.0.0")
    ap.add_argument("--program-status", default="green", choices=("green", "amber", "red"))
    ap.add_argument("--rollback-count", type=int, default=0)
    ap.add_argument("--manifest-out", default="", help="Optional output path for bundle manifest JSON")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    portfolio_out = out_dir / "portfolio-scorecard.json"
    kpi_out = out_dir / "kpi-weekly.json"
    kpi_contract_out = out_dir / "kpi-contract-check.json"
    cross_contract_out = out_dir / "top-tier-contract-check.json"

    portfolio_cmd = [
        sys.executable,
        "scripts/build_portfolio_scorecard.py",
        "--in",
        args.input,
        "--out",
        str(portfolio_out),
        "--schema-version",
        args.schema_version,
        "--window-start",
        args.window_start,
        "--window-end",
        args.window_end,
    ]
    if args.generated_at:
        portfolio_cmd += ["--generated-at", args.generated_at]
    _run(portfolio_cmd)

    _run(
        [
            sys.executable,
            "scripts/build_kpi_weekly_snapshot.py",
            "--portfolio-scorecard",
            str(portfolio_out),
            "--out",
            str(kpi_out),
            "--week-ending",
            args.window_end,
            "--program-status",
            args.program_status,
            "--rollback-count",
            str(args.rollback_count),
        ]
    )

    _run(
        [
            sys.executable,
            "scripts/check_kpi_weekly_contract.py",
            "--schema",
            "docs/kpi-schema.v1.json",
            "--payload",
            str(kpi_out),
            "--out",
            str(kpi_contract_out),
        ]
    )

    _run(
        [
            sys.executable,
            "scripts/check_top_tier_reporting_contract.py",
            "--portfolio-scorecard",
            str(portfolio_out),
            "--kpi-weekly",
            str(kpi_out),
            "--out",
            str(cross_contract_out),
        ]
    )

    manifest = {
        "ok": True,
        "window": {"start": args.window_start, "end": args.window_end},
        "program_status": args.program_status,
        "artifacts": {
            "portfolio_scorecard": {"path": str(portfolio_out), "sha256": _sha256(portfolio_out)},
            "kpi_weekly": {"path": str(kpi_out), "sha256": _sha256(kpi_out)},
            "kpi_contract_check": {"path": str(kpi_contract_out), "sha256": _sha256(kpi_contract_out)},
            "top_tier_contract_check": {"path": str(cross_contract_out), "sha256": _sha256(cross_contract_out)},
        },
    }

    if args.manifest_out:
        manifest_path = Path(args.manifest_out)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"wrote bundle to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
