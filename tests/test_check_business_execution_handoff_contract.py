from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_business_execution_handoff_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_handoff_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
handoff_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(handoff_contract)


def test_validate_handoff_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-handoff.v1",
        "week1_status": "go",
        "week1_start_date": "2026-04-28",
        "progress_gate": "pass",
        "progress_completion_percent": 100.0,
        "history_records": 2,
        "latest_gate_counts": {"pass": 1, "conditional-pass": 1, "fail": 0},
        "next_tasks": [],
        "recommended_command": None,
    }
    assert handoff_contract.validate_handoff_contract(payload) == []


def test_main_fails_when_required_fields_missing(tmp_path: Path) -> None:
    artifact = tmp_path / "handoff.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-handoff.v1",
                "week1_status": "go",
            }
        ),
        encoding="utf-8",
    )
    rc = handoff_contract.main(["--artifact", str(artifact)])
    assert rc == 1
