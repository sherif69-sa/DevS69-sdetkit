from __future__ import annotations

import json

import pytest

from sdetkit.pr_guardrail_outcome_memory import (
    append_pr_guardrail_outcome_memory,
    build_pr_guardrail_outcome_record,
    load_pr_guardrail_outcome_memory,
    render_pr_guardrail_outcome_summary_markdown,
    summarize_pr_guardrail_outcome_memory,
)


def test_build_pr_guardrail_outcome_record_normalizes_fields():
    record = build_pr_guardrail_outcome_record(
        candidate_key=" diagnosis:PRE_COMMIT_FORMAT_DRIFT ",
        decision_status=" READY_FOR_PR_BRANCH_REVIEW ",
        target_branch=" maintenance/pre-commit-format-drift ",
        outcome_status=" merged ",
        pr_number="1181",
        merged=True,
        approvals=["dry_run_plan_approved", "human_reviewed_policy_pr", "human_reviewed_policy_pr", ""],
        artifacts=["dry-run-outcome.json", "dry-run-command-log.txt", "dry-run-outcome.json"],
        blockers=[" ", "review completed"],
        elapsed_seconds="42",
    )

    assert record == {
        "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        "decision_status": "READY_FOR_PR_BRANCH_REVIEW",
        "target_branch": "maintenance/pre-commit-format-drift",
        "outcome_status": "merged",
        "pr_number": 1181,
        "merged": True,
        "approvals": ["dry_run_plan_approved", "human_reviewed_policy_pr"],
        "artifacts": ["dry-run-command-log.txt", "dry-run-outcome.json"],
        "blockers": ["review completed"],
        "elapsed_seconds": 42,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"candidate_key": " "}, "candidate_key is required"),
        ({"decision_status": " "}, "decision_status is required"),
        ({"target_branch": " "}, "target_branch is required"),
        ({"outcome_status": " "}, "outcome_status is required"),
    ],
)
def test_build_pr_guardrail_outcome_record_rejects_blank_required_fields(kwargs, message):
    values = {
        "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        "decision_status": "READY_FOR_PR_BRANCH_REVIEW",
        "target_branch": "maintenance/pre-commit-format-drift",
        "outcome_status": "merged",
    }
    values.update(kwargs)

    with pytest.raises(OSError, match=message):
        build_pr_guardrail_outcome_record(**values)


def test_load_missing_outcome_memory_returns_empty_safe_payload(tmp_path):
    payload = load_pr_guardrail_outcome_memory(tmp_path / "missing.json")

    assert payload == {
        "schema_version": "sdetkit.pr_guardrail_outcome_memory.v1",
        "automation_allowed": False,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "records": [],
    }


def test_append_pr_guardrail_outcome_memory_writes_and_sorts_records(tmp_path):
    path = tmp_path / "memory" / "pr-guardrail-outcomes.json"
    later = build_pr_guardrail_outcome_record(
        candidate_key="diagnosis:RUFF_FIXABLE_LINT",
        decision_status="BLOCK_MISSING_APPROVALS",
        target_branch="maintenance/ruff-fixable-lint",
        outcome_status="blocked_missing_approvals",
        pr_number=1200,
        blockers=["required approvals missing"],
    )
    earlier = build_pr_guardrail_outcome_record(
        candidate_key="diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        decision_status="READY_FOR_PR_BRANCH_REVIEW",
        target_branch="maintenance/pre-commit-format-drift",
        outcome_status="merged",
        pr_number=1181,
        merged=True,
    )

    append_pr_guardrail_outcome_memory(path, later)
    payload = append_pr_guardrail_outcome_memory(path, earlier)

    assert path.exists()
    assert [record["candidate_key"] for record in payload["records"]] == [
        "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        "diagnosis:RUFF_FIXABLE_LINT",
    ]
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written == payload
    assert written["automation_allowed"] is False
    assert written["change_allowed_now"] is False
    assert written["direct_to_main_allowed"] is False


def test_load_populated_outcome_memory_preserves_records_but_resets_safety_flags(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "old",
                "automation_allowed": True,
                "change_allowed_now": True,
                "direct_to_main_allowed": True,
                "records": [
                    {
                        "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                        "decision_status": "READY_FOR_PR_BRANCH_REVIEW",
                        "target_branch": "maintenance/pre-commit-format-drift",
                        "outcome_status": "merged",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = load_pr_guardrail_outcome_memory(path)

    assert payload["schema_version"] == "sdetkit.pr_guardrail_outcome_memory.v1"
    assert payload["automation_allowed"] is False
    assert payload["change_allowed_now"] is False
    assert payload["direct_to_main_allowed"] is False
    assert payload["records"][0]["candidate_key"] == "diagnosis:PRE_COMMIT_FORMAT_DRIFT"


def test_summarize_pr_guardrail_outcome_memory_counts_records():
    memory = {
        "records": [
            {
                "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                "decision_status": "READY_FOR_PR_BRANCH_REVIEW",
                "outcome_status": "merged",
                "merged": True,
            },
            {
                "candidate_key": "diagnosis:RUFF_FIXABLE_LINT",
                "decision_status": "BLOCK_MISSING_APPROVALS",
                "outcome_status": "blocked_missing_approvals",
                "merged": False,
            },
            {
                "candidate_key": "diagnosis:RUFF_FIXABLE_LINT",
                "decision_status": "BLOCK_NOT_READY",
                "outcome_status": "blocked_not_ready",
                "merged": False,
            },
        ]
    }

    summary = summarize_pr_guardrail_outcome_memory(memory)

    assert summary == {
        "schema_version": "sdetkit.pr_guardrail_outcome_memory.summary.v1",
        "automation_allowed": False,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "record_count": 3,
        "merged_count": 1,
        "blocked_count": 2,
        "counts_by_outcome_status": {
            "blocked_missing_approvals": 1,
            "blocked_not_ready": 1,
            "merged": 1,
        },
        "counts_by_decision_status": {
            "BLOCK_MISSING_APPROVALS": 1,
            "BLOCK_NOT_READY": 1,
            "READY_FOR_PR_BRANCH_REVIEW": 1,
        },
    }


def test_pr_guardrail_outcome_summary_markdown_is_operator_readable():
    summary = summarize_pr_guardrail_outcome_memory(
        {
            "records": [
                {
                    "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                    "decision_status": "READY_FOR_PR_BRANCH_REVIEW",
                    "outcome_status": "merged",
                    "merged": True,
                }
            ]
        }
    )

    rendered = render_pr_guardrail_outcome_summary_markdown(summary)

    assert rendered.startswith("# PR guardrail outcome memory")
    assert "automation allowed: **False**" in rendered
    assert "change allowed now: **False**" in rendered
    assert "direct-to-main allowed: **False**" in rendered
    assert "records: **1**" in rendered
    assert "merged: **1**" in rendered
    assert "`merged`: 1" in rendered
    assert "`READY_FOR_PR_BRANCH_REVIEW`: 1" in rendered
    assert "does not make repository changes" in rendered
