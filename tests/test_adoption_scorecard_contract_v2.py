from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/check_adoption_scorecard_v2_contract.py", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_adoption_scorecard_v2_contract_validator_passes(tmp_path: Path) -> None:
    payload = {
        "schema_version": "2",
        "score": 82,
        "band": "strong",
        "dimensions": {"onboarding": 20, "release": 22, "ops": 19, "quality": 21},
        "graded_dimensions": {"onboarding": 80, "release": 88, "ops": 76, "quality": 84},
        "weights": {"onboarding": 0.3, "release": 0.25, "ops": 0.2, "quality": 0.25},
        "signals": {
            "onboarding": {},
            "release": {},
            "ops": {},
            "quality": {},
        },
    }
    path = tmp_path / "score.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run("--infile", str(path), "--format", "json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["errors"] == []


def test_adoption_scorecard_v2_contract_validator_fails_on_weights(tmp_path: Path) -> None:
    payload = {
        "schema_version": "2",
        "score": 82,
        "band": "strong",
        "dimensions": {"onboarding": 20, "release": 22, "ops": 19, "quality": 21},
        "graded_dimensions": {"onboarding": 80, "release": 88, "ops": 76, "quality": 84},
        "weights": {"onboarding": 0.3, "release": 0.25, "ops": 0.2, "quality": 0.1},
        "signals": {
            "onboarding": {},
            "release": {},
            "ops": {},
            "quality": {},
        },
    }
    path = tmp_path / "score.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run("--infile", str(path), "--format", "json")
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert any("weights must sum" in err for err in data["errors"])
