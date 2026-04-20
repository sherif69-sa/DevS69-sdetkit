from __future__ import annotations

import argparse

from scripts import check_phase4_governance_contract as contract


def test_adherence_missing_review_timestamp_is_unknown_with_actions() -> None:
    payload, failures = contract._build_adherence_payload(
        argparse.Namespace(review_cadence_days=30, last_review_at="")
    )
    assert payload["adherence_status"] == "unknown"
    assert failures == []
    assert payload["recommended_actions"]


def test_adherence_sorted_lists_and_due_state() -> None:
    payload, failures = contract._build_adherence_payload(
        argparse.Namespace(review_cadence_days=30, last_review_at="2026-04-19")
    )
    assert failures == []
    assert payload["blockers"] == sorted(payload["blockers"])
    assert payload["recommended_actions"] == sorted(payload["recommended_actions"])
    assert payload["adherence_status"] in {"on_track", "due", "overdue"}


def test_adherence_invalid_review_timestamp_flags_failure() -> None:
    payload, failures = contract._build_adherence_payload(
        argparse.Namespace(review_cadence_days=30, last_review_at="04/19/2026")
    )
    assert payload["adherence_status"] == "unknown"
    assert "last_review_at must use YYYY-MM-DD" in failures
