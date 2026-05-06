from __future__ import annotations

from sdetkit.auto_fix_probation_report import (
    build_auto_fix_probation_report,
    render_auto_fix_probation_report_markdown,
)
from sdetkit.safe_fix_candidate_registry import build_safe_fix_candidate_registry


def _record(
    classification: str,
    *,
    merged: bool = True,
    manual_fix_outcome: str = "merged",
    safe_fix_outcome: str = "not_attempted",
) -> dict[str, object]:
    return {
        "classification": classification,
        "surface": "tests",
        "proof_command": "python -m pre_commit run -a",
        "merged": merged,
        "manual_fix_outcome": manual_fix_outcome,
        "safe_fix_outcome": safe_fix_outcome,
    }


def test_probation_report_empty_registry_has_no_candidates():
    payload = build_auto_fix_probation_report({})

    assert payload == {
        "schema_version": "sdetkit.auto_fix.probation_report.v1",
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "candidate_count": 0,
        "counts_by_probation_status": {},
        "probation_rows": [],
    }


def test_probation_report_marks_observe_more_candidates():
    registry = build_safe_fix_candidate_registry()

    payload = build_auto_fix_probation_report(registry)

    assert payload["candidate_count"] == 2
    assert payload["counts_by_probation_status"] == {"NEEDS_MORE_OBSERVATION": 2}
    for row in payload["probation_rows"]:
        assert row["probation_status"] == "NEEDS_MORE_OBSERVATION"
        assert row["automation_allowed"] is False
        assert row["auto_fix_allowed_now"] is False
        assert "required observation count" in " ".join(row["blocking_reasons"])


def test_probation_report_marks_not_ready_when_successes_are_short():
    registry = build_safe_fix_candidate_registry(
        {
            "records": [
                _record("PRE_COMMIT_FORMAT_DRIFT"),
                _record("PRE_COMMIT_FORMAT_DRIFT"),
                _record("PRE_COMMIT_FORMAT_DRIFT", merged=False, manual_fix_outcome="unknown"),
            ]
        },
        candidate_classes=("PRE_COMMIT_FORMAT_DRIFT",),
    )

    payload = build_auto_fix_probation_report(registry)
    row = payload["probation_rows"][0]

    assert payload["counts_by_probation_status"] == {"NEEDS_MORE_SUCCESSFUL_PROOF": 1}
    assert row["probation_status"] == "NEEDS_MORE_SUCCESSFUL_PROOF"
    assert row["observed_history_count"] == 3
    assert row["observed_success_count"] == 2
    assert "not enough successful manual outcomes" in " ".join(row["blocking_reasons"])


def test_probation_report_marks_ready_for_review_when_registry_thresholds_are_met():
    registry = build_safe_fix_candidate_registry(
        {
            "records": [
                _record("RUFF_FIXABLE_LINT", safe_fix_outcome="manual_success"),
                _record("RUFF_FIXABLE_LINT", safe_fix_outcome="manual_success"),
                _record("RUFF_FIXABLE_LINT", safe_fix_outcome="manual_success"),
            ]
        },
        candidate_classes=("RUFF_FIXABLE_LINT",),
    )

    payload = build_auto_fix_probation_report(registry)
    row = payload["probation_rows"][0]

    assert payload["counts_by_probation_status"] == {"READY_FOR_PROBATION_REVIEW": 1}
    assert row["probation_status"] == "READY_FOR_PROBATION_REVIEW"
    assert row["observed_history_count"] == 3
    assert row["observed_success_count"] == 3
    assert row["auto_fix_allowed_now"] is False
    assert "future policy PR" in " ".join(row["blocking_reasons"])


def test_probation_report_blocks_policy_violation_if_candidate_allows_auto_fix_now():
    registry = {
        "candidates": [
            {
                "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                "classification": "PRE_COMMIT_FORMAT_DRIFT",
                "current_status": "READY_FOR_POLICY_PR",
                "observed_history_count": 3,
                "observed_success_count": 3,
                "required_history_count": 3,
                "required_success_count": 3,
                "auto_fix_allowed_now": True,
                "blocking_reason": "unsafe test fixture",
            }
        ]
    }

    payload = build_auto_fix_probation_report(registry)
    row = payload["probation_rows"][0]

    assert payload["counts_by_probation_status"] == {"POLICY_VIOLATION": 1}
    assert row["probation_status"] == "POLICY_VIOLATION"
    assert row["auto_fix_allowed_now"] is False
    assert "must be blocked" in " ".join(row["blocking_reasons"])


def test_probation_report_markdown_is_operator_readable():
    registry = build_safe_fix_candidate_registry(
        {
            "records": [
                _record("PRE_COMMIT_FORMAT_DRIFT"),
                _record("PRE_COMMIT_FORMAT_DRIFT"),
                _record("PRE_COMMIT_FORMAT_DRIFT"),
            ]
        },
        candidate_classes=("PRE_COMMIT_FORMAT_DRIFT",),
    )
    payload = build_auto_fix_probation_report(registry)

    rendered = render_auto_fix_probation_report_markdown(payload)

    assert rendered.startswith("# Auto-fix probation report")
    assert "diagnostic only: **True**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "auto-fix allowed now: **False**" in rendered
    assert "`diagnosis:PRE_COMMIT_FORMAT_DRIFT`" in rendered
    assert "READY_FOR_PROBATION_REVIEW" in rendered
    assert "This report does not enable auto-fix" in rendered
