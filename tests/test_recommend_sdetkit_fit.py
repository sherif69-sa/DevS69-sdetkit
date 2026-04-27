from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/recommend_sdetkit_fit.py").resolve()


def test_recommend_sdetkit_fit_high_profile_json() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-size",
            "large",
            "--team-size",
            "large",
            "--release-frequency",
            "high",
            "--change-failure-impact",
            "high",
            "--compliance-pressure",
            "high",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["fit"] == "high"
    assert payload["segment"] == "medium-to-high-stakes delivery"
    assert payload["score"] >= 14
    assert payload["confidence"] == "high"
    assert isinstance(payload["risk_drivers"], list) and payload["risk_drivers"]


def test_recommend_sdetkit_fit_low_profile_text() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-size",
            "small",
            "--team-size",
            "small",
            "--release-frequency",
            "low",
            "--change-failure-impact",
            "low",
            "--compliance-pressure",
            "low",
            "--format",
            "text",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "SDETKIT_FIT=LOW" in proc.stdout
    assert "lightweight path" in proc.stdout
    assert "confidence:" in proc.stdout
    assert "risk_drivers:" in proc.stdout
