from __future__ import annotations

from sdetkit.safe_fix_candidate_registry import (
    build_safe_fix_candidate_registry,
    render_safe_fix_candidate_registry_markdown,
)


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


def test_candidate_registry_empty_memory_observes_more():
    payload = build_safe_fix_candidate_registry()

    assert payload["schema_version"] == "sdetkit.safe_fix.candidates.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["candidate_count"] == 2
    assert payload["counts_by_status"] == {"OBSERVE_MORE": 2}
    assert [candidate["candidate_key"] for candidate in payload["candidates"]] == [
        "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        "diagnosis:RUFF_FIXABLE_LINT",
    ]
    for candidate in payload["candidates"]:
        assert candidate["automation_allowed"] is False
        assert candidate["auto_fix_allowed_now"] is False
        assert candidate["rollback_required"] is True
        assert candidate["required_history_count"] == 3
        assert candidate["required_success_count"] == 3


def test_candidate_registry_counts_history_and_successes():
    memory = {
        "records": [
            _record("PRE_COMMIT_FORMAT_DRIFT"),
            _record("PRE_COMMIT_FORMAT_DRIFT"),
            _record("PRE_COMMIT_FORMAT_DRIFT", merged=False, manual_fix_outcome="unknown"),
            _record("RUFF_FIXABLE_LINT"),
            _record("PRODUCT_LOGIC_FAILURE"),
        ]
    }

    payload = build_safe_fix_candidate_registry(memory)
    by_class = {candidate["classification"]: candidate for candidate in payload["candidates"]}

    assert by_class["PRE_COMMIT_FORMAT_DRIFT"]["observed_history_count"] == 3
    assert by_class["PRE_COMMIT_FORMAT_DRIFT"]["observed_success_count"] == 2
    assert by_class["PRE_COMMIT_FORMAT_DRIFT"]["current_status"] == "NOT_READY"
    assert by_class["RUFF_FIXABLE_LINT"]["observed_history_count"] == 1
    assert by_class["RUFF_FIXABLE_LINT"]["observed_success_count"] == 1
    assert by_class["RUFF_FIXABLE_LINT"]["current_status"] == "OBSERVE_MORE"
    assert payload["counts_by_status"] == {"NOT_READY": 1, "OBSERVE_MORE": 1}


def test_candidate_registry_ready_for_policy_when_thresholds_are_met():
    memory = {
        "records": [
            _record("PRE_COMMIT_FORMAT_DRIFT"),
            _record("PRE_COMMIT_FORMAT_DRIFT"),
            _record("PRE_COMMIT_FORMAT_DRIFT"),
            _record("RUFF_FIXABLE_LINT", safe_fix_outcome="manual_success"),
            _record("RUFF_FIXABLE_LINT", safe_fix_outcome="manual_success"),
            _record("RUFF_FIXABLE_LINT", safe_fix_outcome="manual_success"),
        ]
    }

    payload = build_safe_fix_candidate_registry(memory)
    by_class = {candidate["classification"]: candidate for candidate in payload["candidates"]}

    assert by_class["PRE_COMMIT_FORMAT_DRIFT"]["current_status"] == "READY_FOR_POLICY_PR"
    assert by_class["RUFF_FIXABLE_LINT"]["current_status"] == "READY_FOR_POLICY_PR"
    assert payload["counts_by_status"] == {"READY_FOR_POLICY_PR": 2}
    for candidate in payload["candidates"]:
        assert candidate["auto_fix_allowed_now"] is False
        assert "Policy" in candidate["blocking_reason"]


def test_candidate_registry_markdown_is_operator_readable():
    payload = build_safe_fix_candidate_registry(
        {"records": [_record("PRE_COMMIT_FORMAT_DRIFT"), _record("PRE_COMMIT_FORMAT_DRIFT")]}
    )

    rendered = render_safe_fix_candidate_registry_markdown(payload)

    assert rendered.startswith("# Safe-fix candidate registry")
    assert "diagnostic only: **True**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "`diagnosis:PRE_COMMIT_FORMAT_DRIFT`" in rendered
    assert "`diagnosis:RUFF_FIXABLE_LINT`" in rendered
    assert "OBSERVE_MORE" in rendered
    assert "This registry is diagnostic-only" in rendered


def test_candidate_registry_can_be_limited_to_one_class():
    payload = build_safe_fix_candidate_registry(candidate_classes=("PRE_COMMIT_FORMAT_DRIFT",))

    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["classification"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert payload["candidates"][0]["category"] == "formatting"
