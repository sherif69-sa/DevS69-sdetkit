from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_executive_report as report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_report() -> None:
    out = report.build_report(
        {"status": "near_finish", "completion_percent": 80},
        {"ready_for_phase2": False, "next_step": "make phase1-next-pass"},
        {"count": 1, "rows": [{"blocker": "doctor", "priority": 100, "recommended_action": "fix"}]},
        {"runs": 2, "pass_rate": 50.0, "avg_duration_ms": 200, "duration_drift_ms": 10},
    )
    assert out["status"] == "near_finish"
    assert out["blocker_count"] == 1


def test_main_missing_required_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = report.main(["--format", "json"])
    assert rc == 1


def test_main_writes_outputs(tmp_path: Path) -> None:
    finish = tmp_path / "finish.json"
    gate = tmp_path / "gate.json"
    blockers = tmp_path / "blockers.json"
    telemetry = tmp_path / "telemetry.json"
    out_json = tmp_path / "out" / "exec.json"
    out_md = tmp_path / "out" / "exec.md"

    _write(finish, {"status": "early", "completion_percent": 0})
    _write(gate, {"ready_for_phase2": False, "next_step": "make phase1-next"})
    _write(blockers, {"count": 0, "rows": []})
    _write(telemetry, {"runs": 1, "pass_rate": 100.0, "avg_duration_ms": 100, "duration_drift_ms": 0})

    rc = report.main([
        "--finish", str(finish),
        "--gate", str(gate),
        "--blockers", str(blockers),
        "--telemetry", str(telemetry),
        "--out-json", str(out_json),
        "--out-md", str(out_md),
        "--format", "json",
    ])
    assert rc == 0
    assert out_json.exists()
    assert out_md.exists()
