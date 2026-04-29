from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_readiness_threshold_passes(tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text(
        json.dumps(
            {
                "decision": "SHIP",
                "health_score": 95,
                "followup_ready": True,
                "execution_contract_ok": True,
            }
        ),
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "standard": {
                    "min_health_score": 80,
                    "require_followup_ready": True,
                    "require_execution_contract_ok": True,
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "threshold.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_readiness_threshold.py",
            "--dashboard",
            str(dashboard),
            "--profiles",
            str(profiles),
            "--profile",
            "standard",
            "--out",
            str(out),
            "--format",
            "json",
        ],
        check=True,
    )


def test_readiness_threshold_fails(tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text(
        json.dumps(
            {
                "decision": "SHIP",
                "health_score": 60,
                "followup_ready": False,
                "execution_contract_ok": False,
            }
        ),
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "standard": {
                    "min_health_score": 80,
                    "require_followup_ready": True,
                    "require_execution_contract_ok": True,
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "threshold.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_readiness_threshold.py",
            "--dashboard",
            str(dashboard),
            "--profiles",
            str(profiles),
            "--profile",
            "standard",
            "--out",
            str(out),
        ],
        check=False,
    )
    assert proc.returncode == 1


def test_readiness_threshold_skips_non_ship(tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text(
        json.dumps(
            {
                "decision": "NO-SHIP",
                "health_score": 10,
                "followup_ready": False,
                "execution_contract_ok": False,
            }
        ),
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "standard": {
                    "min_health_score": 80,
                    "require_followup_ready": True,
                    "require_execution_contract_ok": True,
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "threshold.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/check_first_proof_readiness_threshold.py",
            "--dashboard",
            str(dashboard),
            "--profiles",
            str(profiles),
            "--profile",
            "standard",
            "--out",
            str(out),
            "--format",
            "json",
        ],
        check=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["enforced"] is False
