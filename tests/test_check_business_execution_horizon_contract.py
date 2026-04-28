from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_business_execution_horizon_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_horizon_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
horizon_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(horizon_contract)


def test_validate_horizon_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-horizon.v1",
        "week1_status": "go",
        "progress_gate": "conditional-pass",
        "completion_percent": 50.0,
        "followup_checkpoint_status": "on-track",
        "focus_mode": "foundation-build",
        "week_2_plan": {"day_6_7": ["A"]},
        "day_90_plan": {"day_90": ["B"]},
    }
    assert horizon_contract.validate_horizon_contract(payload) == []


def test_main_fails_when_focus_mode_invalid(tmp_path: Path) -> None:
    artifact = tmp_path / "horizon.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-horizon.v1",
                "week1_status": "go",
                "progress_gate": "conditional-pass",
                "completion_percent": 50.0,
                "followup_checkpoint_status": "on-track",
                "focus_mode": "invalid",
                "week_2_plan": {"day_6_7": ["A"]},
                "day_90_plan": {"day_90": ["B"]},
            }
        ),
        encoding="utf-8",
    )
    rc = horizon_contract.main(["--artifact", str(artifact)])
    assert rc == 1
