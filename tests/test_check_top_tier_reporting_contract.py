from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_top_tier_reporting_contract_sample_artifacts(tmp_path: Path) -> None:
    portfolio = Path("docs/artifacts/portfolio-scorecard-sample-2026-04-17.json")
    kpi_weekly = Path("docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json")
    out = tmp_path / "contract-check.json"

    cmd = [
        sys.executable,
        "scripts/check_top_tier_reporting_contract.py",
        "--portfolio-scorecard",
        str(portfolio),
        "--kpi-weekly",
        str(kpi_weekly),
        "--out",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    report = json.loads(out.read_text())
    assert report["ok"] is True
    assert report["repo_count"] == 3
    assert report["week_ending"] == "2026-04-17"
