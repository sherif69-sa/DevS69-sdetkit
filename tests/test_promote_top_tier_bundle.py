from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_promote_top_tier_bundle_from_generated_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"

    build_cmd = [
        sys.executable,
        "scripts/build_top_tier_reporting_bundle.py",
        "--input",
        "docs/artifacts/portfolio-input-sample-2026-04-17.jsonl",
        "--out-dir",
        str(bundle_dir),
        "--window-start",
        "2026-04-11",
        "--window-end",
        "2026-04-17",
        "--generated-at",
        "2026-04-17T10:00:00Z",
    ]
    subprocess.run(build_cmd, check=True)

    promote_cmd = [
        sys.executable,
        "scripts/promote_top_tier_bundle.py",
        "--bundle-dir",
        str(bundle_dir),
        "--date-tag",
        "2099-01-01",
    ]
    subprocess.run(promote_cmd, check=True)

    assert Path("docs/artifacts/portfolio-scorecard-sample-2099-01-01.json").is_file()
    assert Path("docs/artifacts/kpi-weekly-from-portfolio-2099-01-01.json").is_file()
    assert Path("docs/artifacts/kpi-weekly-contract-check-2099-01-01.json").is_file()
    assert Path("docs/artifacts/top-tier-contract-check-2099-01-01.json").is_file()

    # cleanup files created by this test in repo workspace
    Path("docs/artifacts/portfolio-scorecard-sample-2099-01-01.json").unlink(missing_ok=True)
    Path("docs/artifacts/kpi-weekly-from-portfolio-2099-01-01.json").unlink(missing_ok=True)
    Path("docs/artifacts/kpi-weekly-contract-check-2099-01-01.json").unlink(missing_ok=True)
    Path("docs/artifacts/top-tier-contract-check-2099-01-01.json").unlink(missing_ok=True)
