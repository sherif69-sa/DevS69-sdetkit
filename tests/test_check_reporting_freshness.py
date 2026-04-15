from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


_REQUIRED_PATTERNS = (
    "portfolio-scorecard-sample-{date}.json",
    "kpi-weekly-from-portfolio-{date}.json",
    "kpi-weekly-contract-check-{date}.json",
    "top-tier-contract-check-{date}.json",
    "top-tier-bundle-manifest-{date}.json",
    "top-tier-bundle-manifest-check-{date}.json",
    "top-tier-artifact-set-check-{date}.json",
)


def _touch_with_date(path: Path, day: str) -> None:
    path.write_text("{}\n")
    ts = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    path.touch()
    path.chmod(0o644)
    # Keep deterministic mtime for freshness checks.
    import os

    os.utime(path, (ts, ts))


def test_check_reporting_freshness_passes_for_fresh_set(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    date_tag = "2026-04-17"
    for pattern in _REQUIRED_PATTERNS:
        _touch_with_date(artifacts / pattern.format(date=date_tag), "2026-04-16")

    out = tmp_path / "freshness.json"
    cmd = [
        sys.executable,
        "scripts/check_reporting_freshness.py",
        "--date-tag",
        date_tag,
        "--artifacts-dir",
        str(artifacts),
        "--reference-date",
        "2026-04-17",
        "--max-age-days",
        "7",
        "--out",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    report = json.loads(out.read_text())
    assert report["ok"] is True
    assert report["missing_count"] == 0
    assert report["stale_count"] == 0
    assert report["checked_count"] == 7


def test_check_reporting_freshness_fails_on_missing_and_stale(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    date_tag = "2026-04-17"

    # Write only one very old file; leave remaining required files missing.
    _touch_with_date(
        artifacts / f"portfolio-scorecard-sample-{date_tag}.json",
        "2026-03-01",
    )

    out = tmp_path / "freshness.json"
    cmd = [
        sys.executable,
        "scripts/check_reporting_freshness.py",
        "--date-tag",
        date_tag,
        "--artifacts-dir",
        str(artifacts),
        "--reference-date",
        "2026-04-17",
        "--max-age-days",
        "7",
        "--out",
        str(out),
    ]
    result = subprocess.run(cmd, check=False)

    assert result.returncode == 1
    report = json.loads(out.read_text())
    assert report["ok"] is False
    assert report["checked_count"] == 1
    assert report["stale_count"] == 1
    assert report["missing_count"] == 6
