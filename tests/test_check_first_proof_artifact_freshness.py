from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REQUIRED = [
    "first-proof-summary.json",
    "health-score.json",
    "doctor-remediate.json",
    "first-proof-learning-rollup.json",
]


def test_freshness_passes_when_all_artifacts_exist(tmp_path: Path) -> None:
    for name in REQUIRED:
        (tmp_path / name).write_text("{}\n", encoding="utf-8")

    out = tmp_path / "artifact-freshness.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_artifact_freshness.py",
            "--artifact-dir",
            str(tmp_path),
            "--max-age-hours",
            "48",
            "--out",
            str(out),
            "--format",
            "json",
        ],
        check=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["missing"] == []
    assert payload["stale"] == []


def test_freshness_fails_when_artifact_missing(tmp_path: Path) -> None:
    (tmp_path / "first-proof-summary.json").write_text("{}\n", encoding="utf-8")
    out = tmp_path / "artifact-freshness.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_artifact_freshness.py",
            "--artifact-dir",
            str(tmp_path),
            "--max-age-hours",
            "48",
            "--out",
            str(out),
        ],
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "health-score.json" in payload["missing"]
