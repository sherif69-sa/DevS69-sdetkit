from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_business_execution_followup_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_followup_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
followup_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(followup_contract)


def test_validate_followup_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-followup.v1",
        "progress_gate": "conditional-pass",
        "escalation_decision": "watch",
        "window_hours": 24,
        "pending_count": 1,
        "next_tasks": ["Task A"],
        "immediate_actions": ["Complete: Task A"],
        "recommended_command": 'python scripts/business_execution_progress.py --done "Task A"',
        "keep_moving": True,
        "history_records": 3,
        "decision_counts": {"none": 0, "watch": 2, "escalate": 1},
        "latest_recorded_at": "2026-04-28T18:00:00+00:00",
        "next_checkpoint_at": "2026-04-29T18:00:00+00:00",
        "checkpoint_status": "on-track",
        "checkpoint_due_in_hours": 12.5,
        "checkpoint_command": "make business-execution-followup",
    }
    assert followup_contract.validate_followup_contract(payload) == []


def test_main_fails_when_keep_moving_is_not_bool(tmp_path: Path) -> None:
    artifact = tmp_path / "followup.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-followup.v1",
                "progress_gate": "conditional-pass",
                "escalation_decision": "watch",
                "window_hours": 24,
                "pending_count": 1,
                "next_tasks": ["Task A"],
                "immediate_actions": ["Complete: Task A"],
                "recommended_command": 'python scripts/business_execution_progress.py --done "Task A"',
                "keep_moving": "yes",
                "history_records": 1,
                "decision_counts": {"none": 0, "watch": 1, "escalate": 0},
                "latest_recorded_at": "2026-04-28T18:00:00+00:00",
                "next_checkpoint_at": "2026-04-29T18:00:00+00:00",
                "checkpoint_status": "on-track",
                "checkpoint_due_in_hours": 12.5,
                "checkpoint_command": "make business-execution-followup",
            }
        ),
        encoding="utf-8",
    )
    rc = followup_contract.main(["--artifact", str(artifact)])
    assert rc == 1
