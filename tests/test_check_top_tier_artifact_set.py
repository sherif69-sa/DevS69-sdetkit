from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_top_tier_artifact_set_for_seed_date(tmp_path: Path) -> None:
    out = tmp_path / "artifact-set-check.json"

    cmd = [
        sys.executable,
        "scripts/check_top_tier_artifact_set.py",
        "--date-tag",
        "2026-04-17",
        "--out",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    report = json.loads(out.read_text())
    assert report["ok"] is True
    assert report["date_tag"] == "2026-04-17"
    assert report["required_count"] == 6
    assert report["found_count"] == 6
    assert report["missing_count"] == 0
    assert report["invalid_json_count"] == 0
    assert len(report["found"]) == 6
    assert report["missing"] == []
    assert report["invalid_json"] == []
    assert report["invalid_json_errors"] == []
    assert len(report["required"]) == 6


def test_check_top_tier_artifact_set_fails_when_missing(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    out = tmp_path / "artifact-set-check.json"

    # Seed only one required artifact for the date; checker should report missing files.
    (artifacts / "portfolio-scorecard-sample-2099-01-01.json").write_text("{}\n")

    cmd = [
        sys.executable,
        "scripts/check_top_tier_artifact_set.py",
        "--date-tag",
        "2099-01-01",
        "--artifacts-dir",
        str(artifacts),
        "--out",
        str(out),
    ]
    result = subprocess.run(cmd, check=False)

    assert result.returncode == 1
    report = json.loads(out.read_text())
    assert report["ok"] is False
    assert report["required_count"] == 6
    assert report["found_count"] == 1
    assert report["missing_count"] == 5
    assert report["invalid_json_count"] == 0
    assert len(report["required"]) == 6
    assert len(report["missing"]) == 5
    assert report["invalid_json"] == []
    assert report["invalid_json_errors"] == []


def test_check_top_tier_artifact_set_fails_on_invalid_json(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    out = tmp_path / "artifact-set-check.json"
    date_tag = "2099-01-02"

    required = [
        "portfolio-scorecard-sample-{date}.json",
        "kpi-weekly-from-portfolio-{date}.json",
        "kpi-weekly-contract-check-{date}.json",
        "top-tier-contract-check-{date}.json",
        "top-tier-bundle-manifest-{date}.json",
        "top-tier-bundle-manifest-check-{date}.json",
    ]
    for pattern in required:
        (artifacts / pattern.format(date=date_tag)).write_text("{}\n")

    # Corrupt one file so existence passes but JSON validity fails.
    (artifacts / f"kpi-weekly-contract-check-{date_tag}.json").write_text("{not-json}\n")

    cmd = [
        sys.executable,
        "scripts/check_top_tier_artifact_set.py",
        "--date-tag",
        date_tag,
        "--artifacts-dir",
        str(artifacts),
        "--out",
        str(out),
    ]
    result = subprocess.run(cmd, check=False)

    assert result.returncode == 1
    report = json.loads(out.read_text())
    assert report["ok"] is False
    assert report["missing_count"] == 0
    assert report["invalid_json_count"] == 1
    assert len(report["invalid_json"]) == 1
    assert len(report["invalid_json_errors"]) == 1
    assert report["invalid_json_errors"][0]["path"].endswith(
        f"kpi-weekly-contract-check-{date_tag}.json"
    )
