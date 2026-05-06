from __future__ import annotations

from sdetkit.auto_fix_dry_run_plan import (
    build_auto_fix_dry_run_plan,
    render_auto_fix_dry_run_plan_markdown,
)


def _proposal(
    candidate_key: str,
    proposal_status: str,
    *,
    auto_fix_allowed_now: bool = False,
) -> dict[str, object]:
    return {
        "candidate_key": candidate_key,
        "classification": candidate_key.removeprefix("diagnosis:"),
        "proposal_status": proposal_status,
        "automation_allowed": False,
        "auto_fix_allowed_now": auto_fix_allowed_now,
        "requires_human_review": True,
        "blocking_reasons": ["policy proposal not approved"],
    }


def test_dry_run_plan_empty_proposals_has_no_plans():
    payload = build_auto_fix_dry_run_plan({})

    assert payload == {
        "schema_version": "sdetkit.auto_fix.dry_run_plan.v1",
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "plan_count": 0,
        "counts_by_dry_run_status": {},
        "plans": [],
    }


def test_dry_run_plan_maps_ready_policy_proposal_to_review_plan():
    payload = build_auto_fix_dry_run_plan(
        {"proposals": [_proposal("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "PROPOSE_POLICY_REVIEW")]}
    )
    plan = payload["plans"][0]

    assert payload["counts_by_dry_run_status"] == {"READY_FOR_DRY_RUN_PLAN_REVIEW": 1}
    assert plan["dry_run_status"] == "READY_FOR_DRY_RUN_PLAN_REVIEW"
    assert plan["automation_allowed"] is False
    assert plan["auto_fix_allowed_now"] is False
    assert plan["requires_human_review"] is True
    assert plan["dry_run_commands"] == [
        "python -m pre_commit run -a",
        "git diff --check",
        "./scripts/pr_preflight.sh",
    ]
    assert "dry-run-command-log.txt" in plan["expected_artifacts"]
    assert "dry-run-diff.patch" in plan["expected_artifacts"]
    assert "human_reviewed_policy_pr" in plan["required_guardrails"]
    assert "pr_only_guardrails" in plan["required_guardrails"]
    assert "human approval" in " ".join(plan["blockers"])


def test_dry_run_plan_maps_waiting_policy_proposal_to_not_ready():
    payload = build_auto_fix_dry_run_plan(
        {"proposals": [_proposal("diagnosis:RUFF_FIXABLE_LINT", "WAIT_FOR_MORE_SUCCESSFUL_PROOF")]}
    )
    plan = payload["plans"][0]

    assert payload["counts_by_dry_run_status"] == {"NOT_READY_FOR_DRY_RUN": 1}
    assert plan["dry_run_status"] == "NOT_READY_FOR_DRY_RUN"
    assert plan["dry_run_commands"] == [
        "python -m ruff check . --fix --diff",
        "python -m ruff format --check .",
        "python -m pre_commit run -a",
    ]
    assert plan["blockers"] == ["policy proposal not approved"]
    assert plan["auto_fix_allowed_now"] is False


def test_dry_run_plan_blocks_policy_violation():
    payload = build_auto_fix_dry_run_plan(
        {
            "proposals": [
                _proposal(
                    "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                    "PROPOSE_POLICY_REVIEW",
                    auto_fix_allowed_now=True,
                )
            ]
        }
    )
    plan = payload["plans"][0]

    assert payload["counts_by_dry_run_status"] == {"BLOCK_POLICY_VIOLATION": 1}
    assert plan["dry_run_status"] == "BLOCK_POLICY_VIOLATION"
    assert plan["auto_fix_allowed_now"] is False
    assert "enabled before dry-run policy approval" in " ".join(plan["blockers"])


def test_dry_run_plan_uses_safe_fallback_command_for_unknown_classification():
    payload = build_auto_fix_dry_run_plan(
        {"proposals": [_proposal("diagnosis:UNKNOWN_REVIEW_REQUIRED", "PROPOSE_POLICY_REVIEW")]}
    )
    plan = payload["plans"][0]

    assert plan["dry_run_commands"] == [
        "python -m sdetkit investigate failure --log <log> --format markdown"
    ]
    assert plan["dry_run_status"] == "READY_FOR_DRY_RUN_PLAN_REVIEW"


def test_dry_run_plan_sorts_plans_by_candidate_key():
    payload = build_auto_fix_dry_run_plan(
        {
            "proposals": [
                _proposal("diagnosis:RUFF_FIXABLE_LINT", "PROPOSE_POLICY_REVIEW"),
                _proposal("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "PROPOSE_POLICY_REVIEW"),
            ]
        }
    )

    assert [plan["candidate_key"] for plan in payload["plans"]] == [
        "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
        "diagnosis:RUFF_FIXABLE_LINT",
    ]


def test_dry_run_plan_markdown_is_operator_readable():
    payload = build_auto_fix_dry_run_plan(
        {"proposals": [_proposal("diagnosis:PRE_COMMIT_FORMAT_DRIFT", "PROPOSE_POLICY_REVIEW")]}
    )

    rendered = render_auto_fix_dry_run_plan_markdown(payload)

    assert rendered.startswith("# Auto-fix dry-run plan")
    assert "diagnostic only: **True**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "auto-fix allowed now: **False**" in rendered
    assert "`diagnosis:PRE_COMMIT_FORMAT_DRIFT`" in rendered
    assert "READY_FOR_DRY_RUN_PLAN_REVIEW" in rendered
    assert "This is a plan only" in rendered
