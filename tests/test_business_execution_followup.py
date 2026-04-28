from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_followup.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_followup_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
followup_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(followup_script)


def test_build_followup_payload_keeps_momentum() -> None:
    progress = {"gate_decision": {"status": "conditional-pass"}}
    next_payload = {
        "next_tasks": ["Task A", "Task B"],
        "recommended_command": 'python scripts/business_execution_progress.py --done "Task A"',
    }
    escalation = {"decision": "watch"}
    payload = followup_script.build_followup_payload(
        progress, next_payload, escalation, window_hours=24
    )
    assert payload["keep_moving"] is True
    assert payload["pending_count"] == 2
    assert payload["immediate_actions"][0] == "Complete: Task A"


def test_main_writes_followup_artifacts(tmp_path: Path) -> None:
    progress = tmp_path / "progress.json"
    next_json = tmp_path / "next.json"
    escalation = tmp_path / "escalation.json"
    out_json = tmp_path / "followup.json"
    out_md = tmp_path / "followup.md"
    history = tmp_path / "followup-history.jsonl"
    rollup = tmp_path / "followup-rollup.json"

    progress.write_text(json.dumps({"gate_decision": {"status": "fail"}}), encoding="utf-8")
    next_json.write_text(json.dumps({"next_tasks": ["A"]}), encoding="utf-8")
    escalation.write_text(json.dumps({"decision": "escalate"}), encoding="utf-8")

    rc = followup_script.main(
        [
            "--progress",
            str(progress),
            "--next",
            str(next_json),
            "--escalation",
            str(escalation),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--history",
            str(history),
            "--history-rollup-out",
            str(rollup),
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["escalation_decision"] == "escalate"
    assert payload["recommended_command"] == "make business-execution-pipeline"
    assert payload["history_records"] == 1
    assert payload["decision_counts"]["escalate"] == 1
    assert payload["checkpoint_status"] == "on-track"
    assert isinstance(payload["next_checkpoint_at"], str)
    assert isinstance(payload["checkpoint_due_in_hours"], (int, float))
    assert payload["checkpoint_command"] == "make business-execution-followup"
    assert out_md.exists()
    assert history.exists()
    assert rollup.exists()
