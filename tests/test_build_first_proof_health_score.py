from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_first_proof_health_score_green(tmp_path: Path) -> None:
    summary = {
        "ok": True,
        "failed_steps": [],
        "steps": [
            {"name": "gate-fast", "returncode": 0},
            {"name": "gate-release", "returncode": 0},
            {"name": "doctor", "returncode": 0},
        ],
    }
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    out_json = tmp_path / "health-score.json"
    out_md = tmp_path / "health-score.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_first_proof_health_score.py",
            "--summary",
            str(summary_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["score"] == 100
    assert payload["decision"] == "GREEN"


def test_build_first_proof_health_score_red(tmp_path: Path) -> None:
    summary = {
        "ok": False,
        "failed_steps": ["gate-release", "doctor"],
        "steps": [
            {"name": "gate-fast", "returncode": 0},
            {"name": "gate-release", "returncode": 1},
            {"name": "doctor", "returncode": 1},
        ],
    }
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    out_json = tmp_path / "health-score.json"
    out_md = tmp_path / "health-score.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_first_proof_health_score.py",
            "--summary",
            str(summary_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["score"] == 10
    assert payload["decision"] == "RED"
    assert payload["reason_count"] >= 2
