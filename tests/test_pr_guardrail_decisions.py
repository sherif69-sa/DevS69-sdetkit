from __future__ import annotations

from sdetkit.pr_guardrail_decisions import (
    build_pr_guardrail_decisions,
    render_pr_guardrail_decisions_markdown,
)


ALL_APPROVALS = [
    "human_reviewed_policy_pr",
    "dry_run_plan_approved",
    "rollback_plan_approved",
    "pr_only_guardrails",
    "clean_worktree_confirmed",
]


def _plan(
    candidate_key: str,
    dry_run_status: str,
    *,
    direct_to_main_allowed: bool = False,
) -> dict[str, object]:
    return {
        "candidate_key": candidate_key,
        "classification": candidate_key.removeprefix("diagnosis:"),
        "dry_run_status": dry_run_status,
        "direct_to_main_allowed": direct_to_main_allowed,
        "dry_run_commands": ["python -m pre_commit run -a", "./scripts/pr_preflight.sh"],
        "expected_artifacts": ["dry-run-command-log.txt", "dry-run-outcome.json"],
    }


def test_pr_guardrail_decisions_empty_plan_has_no_decisions():
    payload = build_pr_guardrail_decisions({})

    assert payload == {
        "schema_version": "sdetkit.pr_guardrail_decisions.v1",
        "automation_allowed": False,
        "change_allowed_now": False,
        "direct_to_main_allowed": False,
        "decision_count": 0,
        "counts_by_decision_status": {},
        "decisions": [],
    }


def test_pr_guardrail_decisions_ready_when_all_approvals_present():
    payload = build_pr_guardrail_decisions(
        {
            "plans": [
                _plan("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "READY_FOR_DRY_RUN_PLAN_REVIEW")
            ]
        },
        approvals=ALL_APPROVALS,
    )
    decision = payload["decisions"][0]

    assert payload["counts_by_decision_status"] == {"READY_FOR_PR_BRANCH_REVIEW": 1}
    assert decision["decision_status"] == "READY_FOR_PR_BRANCH_REVIEW"
    assert decision["change_allowed_now"] is False
    assert decision["direct_to_main_allowed"] is False
    assert decision["pr_only"] is True
    assert decision["requires_human_review"] is True
    assert decision["target_branch"] == "maintenance/pre-commit-format-drift"
    assert decision["missing_approvals"] == []
    assert decision["review_commands"] == ["python -m pre_commit run -a", "./scripts/pr_preflight.sh"]
    assert decision["expected_artifacts"] == ["dry-run-command-log.txt", "dry-run-outcome.json"]
    assert decision["blockers"] == []


def test_pr_guardrail_decisions_block_missing_approvals():
    payload = build_pr_guardrail_decisions(
        {
            "plans": [
                _plan("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "READY_FOR_DRY_RUN_PLAN_REVIEW")
            ]
        },
        approvals=["human_reviewed_policy_pr", "dry_run_plan_approved"],
    )
    decision = payload["decisions"][0]

    assert payload["counts_by_decision_status"] == {"BLOCK_MISSING_APPROVALS": 1}
    assert decision["decision_status"] == "BLOCK_MISSING_APPROVALS"
    assert decision["missing_approvals"] == [
        "rollback_plan_approved",
        "pr_only_guardrails",
        "clean_worktree_confirmed",
    ]
    assert "Required approvals are missing" in " ".join(decision["blockers"])
    assert decision["change_allowed_now"] is False


def test_pr_guardrail_decisions_block_not_ready_plan():
    payload = build_pr_guardrail_decisions(
        {"plans": [_plan("diagnosis:RUFF_FIXABLE_LINT", "NOT_READY_FOR_DRY_RUN")]},
        approvals=ALL_APPROVALS,
    )
    decision = payload["decisions"][0]

    assert payload["counts_by_decision_status"] == {"BLOCK_NOT_READY": 1}
    assert decision["decision_status"] == "BLOCK_NOT_READY"
    assert decision["target_branch"] == "maintenance/ruff-fixable-lint"
    assert decision["missing_approvals"] == []
    assert "not ready" in " ".join(decision["blockers"])


def test_pr_guardrail_decisions_block_direct_to_main_signal():
    payload = build_pr_guardrail_decisions(
        {
            "plans": [
                _plan(
                    "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                    "READY_FOR_DRY_RUN_PLAN_REVIEW",
                    direct_to_main_allowed=True,
                )
            ]
        },
        approvals=ALL_APPROVALS,
    )
    decision = payload["decisions"][0]

    assert payload["counts_by_decision_status"] == {"BLOCK_DIRECT_TO_MAIN": 1}
    assert decision["decision_status"] == "BLOCK_DIRECT_TO_MAIN"
    assert decision["direct_to_main_allowed"] is False
    assert "Direct-to-main changes are blocked" in " ".join(decision["blockers"])


def test_pr_guardrail_decisions_sort_by_candidate_key():
    payload = build_pr_guardrail_decisions(
        {
            "plans": [
                _plan("diagnosis:RUFF_FIXABLE_LINT", "READY_FOR_DRY_RUN_PLAN_REVIEW"),
                _plan("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "READY_FOR_DRY_RUN_PLAN_REVIEW"),
            ]
        },
        approvals=ALL_APPROVALS,
    )

    assert [decision["candidate_key"] for decision in payload["decisions"]] == [
        "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        "diagnosis:RUFF_FIXABLE_LINT",
    ]


def test_pr_guardrail_decisions_markdown_is_operator_readable():
    payload = build_pr_guardrail_decisions(
        {
            "plans": [
                _plan("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "READY_FOR_DRY_RUN_PLAN_REVIEW")
            ]
        },
        approvals=ALL_APPROVALS,
    )

    rendered = render_pr_guardrail_decisions_markdown(payload)

    assert rendered.startswith("# PR guardrail decisions")
    assert "automation allowed: **False**" in rendered
    assert "change allowed now: **False**" in rendered
    assert "direct-to-main allowed: **False**" in rendered
    assert "`diagnosis:PRE_COMMIT_FORMAT_DRIFT`" in rendered
    assert "READY_FOR_PR_BRANCH_REVIEW" in rendered
    assert "This layer only decides" in rendered
