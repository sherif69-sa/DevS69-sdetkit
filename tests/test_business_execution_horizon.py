from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_horizon.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_horizon_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
horizon_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(horizon_script)


def test_build_horizon_payload_contains_week2_and_day90() -> None:
    week1 = {"status": "go"}
    progress = {"task_summary": {"completed": 0, "completion_percent": 0.0}, "gate_decision": {"status": "conditional-pass"}}
    followup = {"checkpoint_status": "on-track"}
    payload = horizon_script.build_horizon_payload(week1, progress, followup)
    assert payload["focus_mode"] == "foundation-build"
    assert "day_6_7" in payload["week_2_plan"]
    assert "day_90" in payload["day_90_plan"]


def test_main_writes_horizon_artifacts(tmp_path: Path) -> None:
    week1 = tmp_path / "week1.json"
    progress = tmp_path / "progress.json"
    followup = tmp_path / "followup.json"
    out_json = tmp_path / "horizon.json"
    out_md = tmp_path / "horizon.md"
    week1.write_text(json.dumps({"status": "go"}), encoding="utf-8")
    progress.write_text(
        json.dumps({"task_summary": {"completed": 4, "completion_percent": 66.7}, "gate_decision": {"status": "conditional-pass"}}),
        encoding="utf-8",
    )
    followup.write_text(json.dumps({"checkpoint_status": "on-track"}), encoding="utf-8")
    rc = horizon_script.main(
        [
            "--week1",
            str(week1),
            "--progress",
            str(progress),
            "--followup",
            str(followup),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["focus_mode"] == "execution-acceleration"
    assert out_md.exists()
