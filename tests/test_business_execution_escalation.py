from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_escalation.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_escalation_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
escalation_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(escalation_script)


def test_build_escalation_payload_returns_watch_for_conditional_pass() -> None:
    week1 = {"status": "go", "owner_assignments": {"program_owner": "Founder"}}
    progress = {
        "gate_decision": {"status": "conditional-pass"},
        "task_summary": {"completion_percent": 40.0},
    }
    next_payload = {"next_tasks": ["Task A", "Task B"]}
    handoff = {"recommended_command": "python scripts/business_execution_progress.py --done \"Task A\""}
    payload = escalation_script.build_escalation_payload(week1, progress, next_payload, handoff)
    assert payload["decision"] == "watch"
    assert payload["pending_count"] == 2
    assert payload["owners_to_ping"] == ["Founder"]


def test_main_writes_escalation_artifacts(tmp_path: Path) -> None:
    week1 = tmp_path / "week1.json"
    progress = tmp_path / "progress.json"
    next_json = tmp_path / "next.json"
    handoff = tmp_path / "handoff.json"
    out_json = tmp_path / "escalation.json"
    out_md = tmp_path / "escalation.md"

    week1.write_text(
        json.dumps(
            {
                "status": "needs-owner-assignment",
                "owner_assignments": {"program_owner": "TBD"},
            }
        ),
        encoding="utf-8",
    )
    progress.write_text(
        json.dumps({"gate_decision": {"status": "fail"}, "task_summary": {"completion_percent": 0.0}}),
        encoding="utf-8",
    )
    next_json.write_text(json.dumps({"next_tasks": ["Assign owner"]}), encoding="utf-8")
    handoff.write_text(json.dumps({"recommended_command": "make business-execution-start"}), encoding="utf-8")

    rc = escalation_script.main(
        [
            "--week1",
            str(week1),
            "--progress",
            str(progress),
            "--next",
            str(next_json),
            "--handoff",
            str(handoff),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "escalate"
    assert out_md.exists()


def test_build_escalation_payload_keeps_watch_when_only_owners_missing() -> None:
    week1 = {"status": "needs-owner-assignment", "owners": {"program_owner": "TBD"}}
    progress = {
        "gate_decision": {"status": "conditional-pass"},
        "task_summary": {"completion_percent": 60.0},
    }
    next_payload = {"next_tasks": ["Task A"]}
    handoff = {"recommended_command": "python scripts/business_execution_progress.py --done \"Task A\""}
    payload = escalation_script.build_escalation_payload(week1, progress, next_payload, handoff)
    assert payload["decision"] == "watch"
