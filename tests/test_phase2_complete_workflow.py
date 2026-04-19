from __future__ import annotations

from scripts import phase2_complete_workflow


def test_build_summary_marks_failure_when_any_step_fails() -> None:
    payload = phase2_complete_workflow.build_summary(
        [{"command": "a", "ok": True}, {"command": "b", "ok": False}]
    )
    assert payload["ok"] is False
    assert payload["failed_steps"] == ["b"]


def test_build_summary_ok_when_all_steps_pass() -> None:
    payload = phase2_complete_workflow.build_summary(
        [{"command": "a", "ok": True}, {"command": "b", "ok": True}]
    )
    assert payload["ok"] is True
    assert payload["failed_steps"] == []
