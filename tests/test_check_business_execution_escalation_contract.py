from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_business_execution_escalation_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_escalation_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
escalation_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(escalation_contract)


def test_validate_escalation_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-escalation.v1",
        "week1_status": "go",
        "progress_gate": "conditional-pass",
        "completion_percent": 55.0,
        "pending_count": 2,
        "pending_tasks": ["Task A", "Task B"],
        "decision": "watch",
        "reasons": ["Execution is in progress and requires daily follow-up."],
        "owners_to_ping": ["Founder"],
        "recommended_actions": ["Close the top pending tasks by end of day."],
    }
    assert escalation_contract.validate_escalation_contract(payload) == []


def test_main_fails_when_decision_invalid(tmp_path: Path) -> None:
    artifact = tmp_path / "escalation.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-escalation.v1",
                "week1_status": "go",
                "progress_gate": "pass",
                "completion_percent": 100.0,
                "pending_count": 0,
                "pending_tasks": [],
                "decision": "invalid",
                "reasons": [],
                "owners_to_ping": [],
                "recommended_actions": [],
            }
        ),
        encoding="utf-8",
    )
    rc = escalation_contract.main(["--artifact", str(artifact)])
    assert rc == 1
