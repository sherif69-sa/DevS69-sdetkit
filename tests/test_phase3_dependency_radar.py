from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "phase3_dependency_radar.py"
_SPEC = importlib.util.spec_from_file_location("phase3_dependency_radar_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
phase3_radar = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(phase3_radar)


def test_build_radar_marks_breach_when_threshold_exceeded() -> None:
    audit = {
        "summary": {
            "critical_upgrade_signals": 1,
            "high_priority_upgrade_signals": 0,
            "actionable_packages": 3,
        }
    }
    policy = {
        "thresholds": {
            "critical_upgrade_signals_max": 0,
            "high_priority_upgrade_signals_max": 2,
            "actionable_packages_max": 10,
        }
    }
    radar = phase3_radar.build_radar(audit_payload=audit, policy=policy)
    assert radar["threshold_check"]["breach"] is True
    assert radar["threshold_check"]["reasons"]


def test_main_writes_radar_from_input_files(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    policy = tmp_path / "policy.json"
    out = tmp_path / "radar.json"
    audit.write_text(
        json.dumps(
            {
                "summary": {
                    "critical_upgrade_signals": 0,
                    "high_priority_upgrade_signals": 1,
                    "actionable_packages": 2,
                }
            }
        ),
        encoding="utf-8",
    )
    policy.write_text(
        json.dumps(
            {
                "thresholds": {
                    "critical_upgrade_signals_max": 0,
                    "high_priority_upgrade_signals_max": 2,
                    "actionable_packages_max": 10,
                }
            }
        ),
        encoding="utf-8",
    )
    rc = phase3_radar.main(
        ["--audit-json", str(audit), "--policy-json", str(policy), "--out", str(out)]
    )
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["threshold_check"]["breach"] is False
