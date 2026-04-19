from __future__ import annotations

from scripts import phase2_progress_report


def test_build_progress_zero_when_no_inputs() -> None:
    payload = phase2_progress_report.build_progress({}, {})
    assert payload["completion_percent"] == 0.0
    assert payload["ok"] is False


def test_build_progress_full_when_all_markers_pass() -> None:
    payload = phase2_progress_report.build_progress(
        {"ok": True},
        {
            "ok": True,
            "steps": [
                {"command": "python -m sdetkit phase2-hardening-closeout", "ok": True},
                {"command": "python -m sdetkit phase2-wrap-handoff-closeout", "ok": True},
            ],
        },
    )
    assert payload["completion_percent"] == 100.0
    assert payload["ok"] is True
