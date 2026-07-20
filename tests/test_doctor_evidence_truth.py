from __future__ import annotations

from sdetkit.doctor import _build_quality_summary


def test_quality_summary_marks_unavailable_checks_without_false_failures() -> None:
    summary = _build_quality_summary(
        {"ascii": {"ok": True, "severity": "medium"}},
        selected_checks=["pyproject", "venv", "dev_tools", "ascii"],
    )

    assert summary["selected_checks"] == 4
    assert summary["actionable_checks"] == 1
    assert summary["passed_checks"] == 1
    assert summary["failed_checks"] == 0
    assert summary["skipped_checks"] == 3
    assert summary["pass_rate"] == 100
    assert summary["failed_check_ids"] == []
    assert summary["unavailable_check_ids"] == ["pyproject", "venv", "dev_tools"]


def test_quality_summary_still_counts_real_failed_checks() -> None:
    summary = _build_quality_summary(
        {
            "ascii": {"ok": True, "severity": "medium"},
            "deps": {"ok": False, "severity": "high", "fix": [], "evidence": []},
        },
        selected_checks=["ascii", "deps"],
    )

    assert summary["failed_checks"] == 1
    assert summary["failed_check_ids"] == ["deps"]
    assert summary["highest_failure_severity"] == "high"
    assert summary["unavailable_check_ids"] == []
