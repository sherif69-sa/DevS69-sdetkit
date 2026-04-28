from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_business_execution_progress_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_progress_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
progress_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(progress_contract)


def test_validate_progress_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-progress.v1",
        "task_summary": {"completed": 1, "total": 2, "completion_percent": 50.0},
        "tasks": [{"task": "A", "done": True}, {"task": "B", "done": False}],
        "gate_decision": {"status": "conditional-pass", "reason": "Execution in progress."},
    }
    assert progress_contract.validate_progress_contract(payload) == []


def test_main_fails_for_invalid_gate_status(tmp_path: Path) -> None:
    artifact = tmp_path / "progress.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-progress.v1",
                "task_summary": {"completed": 0, "total": 1, "completion_percent": 0.0},
                "tasks": [{"task": "A", "done": False}],
                "gate_decision": {"status": "green", "reason": "x"},
            }
        ),
        encoding="utf-8",
    )
    rc = progress_contract.main(["--artifact", str(artifact)])
    assert rc == 1
