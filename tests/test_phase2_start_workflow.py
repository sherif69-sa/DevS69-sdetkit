from __future__ import annotations

from scripts import phase2_start_workflow


def test_build_summary_reports_failure_actions() -> None:
    summary = phase2_start_workflow.build_summary(
        [
            {"command": "a", "ok": True},
            {"command": "b", "ok": False},
        ]
    )
    assert summary["ok"] is False
    assert summary["failed_steps"] == ["b"]
    assert summary["next_actions"] == ["Fix failing step: b"]


def test_build_summary_ok_when_all_steps_pass() -> None:
    summary = phase2_start_workflow.build_summary(
        [
            {"command": "a", "ok": True},
            {"command": "b", "ok": True},
        ]
    )
    assert summary["ok"] is True
    assert summary["failed_steps"] == []
    assert summary["next_actions"] == []
