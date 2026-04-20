from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_top_tier_reporting_bundle_generates_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "bundle"
    manifest = tmp_path / "bundle-manifest.json"

    cmd = [
        sys.executable,
        "scripts/build_top_tier_reporting_bundle.py",
        "--input",
        "docs/artifacts/portfolio-input-sample-2026-04-17.jsonl",
        "--out-dir",
        str(out_dir),
        "--window-start",
        "2026-04-11",
        "--window-end",
        "2026-04-17",
        "--generated-at",
        "2026-04-17T10:00:00Z",
        "--manifest-out",
        str(manifest),
    ]
    subprocess.run(cmd, check=True)

    portfolio = json.loads((out_dir / "portfolio-scorecard.json").read_text())
    kpi = json.loads((out_dir / "kpi-weekly.json").read_text())
    kpi_check = json.loads((out_dir / "kpi-contract-check.json").read_text())
    cross_check = json.loads((out_dir / "top-tier-contract-check.json").read_text())
    bundle_manifest = json.loads(manifest.read_text())

    assert portfolio["schema_name"] == "sdetkit.portfolio.aggregate"
    assert kpi["schema_version"] == "1.0.0"
    assert kpi_check["ok"] is True
    assert cross_check["ok"] is True
    assert bundle_manifest["ok"] is True
    assert bundle_manifest["artifacts"]["portfolio_scorecard"]["path"].endswith(
        "portfolio-scorecard.json"
    )
