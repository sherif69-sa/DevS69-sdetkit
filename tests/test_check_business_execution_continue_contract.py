from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_business_execution_continue_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_continue_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
continue_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(continue_contract)


def test_validate_continue_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-continue.v1",
        "checkpoint_status": "on-track",
        "keep_moving": True,
        "selected_command": 'python scripts/business_execution_progress.py --done "Task A"',
        "reason": "Execution should keep moving; run recommended command.",
        "should_run_now": True,
    }
    assert continue_contract.validate_continue_contract(payload) == []


def test_main_fails_for_invalid_checkpoint_status(tmp_path: Path) -> None:
    artifact = tmp_path / "continue.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-continue.v1",
                "checkpoint_status": "later",
                "keep_moving": True,
                "selected_command": "make business-execution-followup",
                "reason": "x",
                "should_run_now": True,
            }
        ),
        encoding="utf-8",
    )
    rc = continue_contract.main(["--artifact", str(artifact)])
    assert rc == 1
