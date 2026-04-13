from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/check_observability_v2_contract.py", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_observability_contract_validator_passes_with_snapshot(tmp_path: Path) -> None:
    payload = {
        "status": "ok",
        "contract_version": "sdetkit.serve.contract.v1",
        "observability_contract_version": "2",
        "service": "sdetkit",
        "captured_at": "2026-04-13T00:00:00Z",
        "freshness_summary": {
            "present": 1,
            "missing": 4,
            "invalid_json": 0,
            "stale": 4,
            "fresh": 1,
        },
        "observability": {
            key: {
                "state": "missing",
                "path": f".sdetkit/out/{key}.json",
                "artifact_mtime": None,
                "freshness_age_seconds": None,
                "stale": True,
                "stale_threshold_seconds": 86400,
            }
            for key in (
                "golden_path_health",
                "canonical_path_drift",
                "legacy_command_analyzer",
                "adoption_scorecard",
                "operator_onboarding_summary",
            )
        },
    }
    infile = tmp_path / "obs.json"
    infile.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run("--infile", str(infile), "--format", "json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True


def test_observability_contract_validator_fails_without_summary(tmp_path: Path) -> None:
    payload = {
        "status": "ok",
        "observability_contract_version": "2",
        "captured_at": "2026-04-13T00:00:00Z",
        "observability": {},
    }
    infile = tmp_path / "obs.json"
    infile.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run("--infile", str(infile), "--format", "json")
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert any("freshness_summary" in err for err in data["errors"])
