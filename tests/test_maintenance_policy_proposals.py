from __future__ import annotations

from sdetkit.maintenance_policy_proposals import (
    build_maintenance_policy_proposals,
    render_maintenance_policy_proposals_markdown,
)


def _row(
    candidate_key: str,
    probation_status: str,
    *,
    auto_fix_allowed_now: bool = False,
    history: int = 0,
    successes: int = 0,
) -> dict[str, object]:
    return {
        "candidate_key": candidate_key,
        "classification": candidate_key.removeprefix("diagnosis:"),
        "probation_status": probation_status,
        "observed_history_count": history,
        "observed_success_count": successes,
        "auto_fix_allowed_now": auto_fix_allowed_now,
        "blocking_reasons": ["policy gate not complete"],
    }


def test_policy_proposals_empty_report_has_no_proposals():
    payload = build_maintenance_policy_proposals({})

    assert payload == {
        "schema_version": "sdetkit.maintenance.policy_proposals.v1",
        "diagnostic_only": True,
        "automation_allowed": False,
        "auto_fix_allowed_now": False,
        "proposal_count": 0,
        "counts_by_proposal_status": {},
        "proposals": [],
    }


def test_policy_proposals_map_probation_statuses():
    report = {
        "probation_rows": [
            _row(
                "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                "READY_FOR_PROBATION_REVIEW",
                history=3,
                successes=3,
            ),
            _row(
                "diagnosis:RUFF_FIXABLE_LINT",
                "NEEDS_MORE_SUCCESSFUL_PROOF",
                history=3,
                successes=2,
            ),
            _row(
                "diagnosis:UNKNOWN",
                "NEEDS_MORE_OBSERVATION",
                history=1,
                successes=1,
            ),
        ]
    }

    payload = build_maintenance_policy_proposals(report)
    by_key = {proposal["candidate_key"]: proposal for proposal in payload["proposals"]}

    assert payload["proposal_count"] == 3
    assert payload["counts_by_proposal_status"] == {
        "PROPOSE_POLICY_REVIEW": 1,
        "WAIT_FOR_MORE_OBSERVATION": 1,
        "WAIT_FOR_MORE_SUCCESSFUL_PROOF": 1,
    }
    assert by_key["diagnosis:PRE_COMMIT_FORMAT_DRIFT"]["proposal_status"] == "PROPOSE_POLICY_REVIEW"
    assert by_key["diagnosis:PRE_COMMIT_FORMAT_DRIFT"]["requires_human_review"] is True
    assert by_key["diagnosis:PRE_COMMIT_FORMAT_DRIFT"]["auto_fix_allowed_now"] is False
    assert by_key["diagnosis:RUFF_FIXABLE_LINT"]["proposal_status"] == "WAIT_FOR_MORE_SUCCESSFUL_PROOF"
    assert by_key["diagnosis:UNKNOWN"]["proposal_status"] == "WAIT_FOR_MORE_OBSERVATION"


def test_policy_proposals_block_policy_violation():
    payload = build_maintenance_policy_proposals(
        {
            "probation_rows": [
                _row(
                    "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                    "READY_FOR_PROBATION_REVIEW",
                    auto_fix_allowed_now=True,
                    history=3,
                    successes=3,
                )
            ]
        }
    )
    proposal = payload["proposals"][0]

    assert payload["counts_by_proposal_status"] == {"BLOCK_POLICY_VIOLATION": 1}
    assert proposal["proposal_status"] == "BLOCK_POLICY_VIOLATION"
    assert proposal["automation_allowed"] is False
    assert proposal["auto_fix_allowed_now"] is False
    assert "Block this candidate" in proposal["recommended_next_step"]


def test_policy_proposals_include_required_future_gates():
    payload = build_maintenance_policy_proposals(
        {
            "probation_rows": [
                _row(
                    "diagnosis:RUFF_FIXABLE_LINT",
                    "READY_FOR_PROBATION_REVIEW",
                    history=3,
                    successes=3,
                )
            ]
        }
    )
    proposal = payload["proposals"][0]

    assert proposal["policy_requirements"] == [
        "human_reviewed_policy_pr",
        "dry_run_plan",
        "rollback_plan",
        "pr_only_guardrails",
        "post_merge_outcome_memory",
    ]
    assert "policy proposal PR" in proposal["recommended_next_step"]


def test_policy_proposals_markdown_is_operator_readable():
    payload = build_maintenance_policy_proposals(
        {
            "probation_rows": [
                _row(
                    "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
                    "READY_FOR_PROBATION_REVIEW",
                    history=3,
                    successes=3,
                )
            ]
        }
    )

    rendered = render_maintenance_policy_proposals_markdown(payload)

    assert rendered.startswith("# Maintenance policy proposals")
    assert "diagnostic only: **True**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "auto-fix allowed now: **False**" in rendered
    assert "`diagnosis:PRE_COMMIT_FORMAT_DRIFT`" in rendered
    assert "PROPOSE_POLICY_REVIEW" in rendered
    assert "These are policy proposals only" in rendered
