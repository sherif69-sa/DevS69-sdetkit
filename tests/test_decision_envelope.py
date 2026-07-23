import json
from pathlib import Path

import pytest

from sdetkit.decision_envelope import (
    AUTHORITY_FIELDS,
    build_decision_envelope,
    render_decision_envelope_markdown,
    write_decision_envelope,
)

REPOSITORY = "sherif69-sa/DevS69-sdetkit"
COMMIT_SHA = "a" * 40


def _failure_vector() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.failure_vector.v1",
        "failure_class": "formatter_only",
        "failure_type": "formatter_only",
        "risk": "low",
        "scope": "pr_owned_only",
        "actual_failure": "1 file would be reformatted",
        "first_failing_line": "ruff format...Failed",
        "affected_files": ["tests/test_widget.py"],
        "local_repro_command": "python -m ruff format --check tests/test_widget.py",
        "owner_hint": "tests/test_widget.py",
        "contract": {
            "failure_kind": "formatter_only",
            "ownership_area": "tests/test_widget.py",
            "recommended_next_human_action": "review generated fix and run proof commands",
            "automation_allowed": False,
            "patch_application_allowed": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_claim": False,
        },
    }


def _safety_gate() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.safety_gate.v1",
        "failure_kind": "formatter_only",
        "ownership_area": "tests/test_widget.py",
        "risk": "low",
        "safe_fix_allowed": True,
        "review_first": False,
        "security_relevance": False,
        "recommended_next_human_action": "review generated fix and run proof commands",
        "proof_commands": [
            "python -m ruff format --check tests/test_widget.py",
            "make proof-after-format",
        ],
        "blocked_actions": ["delete or weaken tests"],
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }


def _proposal() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.formatter_policy_proposal.v1",
        "status": "passed",
        "proposal_status": "eligible_for_human_policy_proposal",
        "proposal_eligible": True,
        "candidate_family": "formatter_only",
        "source_repository": REPOSITORY,
        "source_commit_sha": COMMIT_SHA,
        "source_pr_number": 2141,
        "branch_execution_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "publication_authorized": False,
        "security_dismissal_allowed": False,
        "semantic_equivalence_proven": False,
    }


def test_builds_exact_head_envelope_with_deterministic_identity() -> None:
    first = build_decision_envelope(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        failure_vector=_failure_vector(),
        safety_gate=_safety_gate(),
        quality_proof_commands=("python -m pytest -q",),
    )
    second = build_decision_envelope(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        failure_vector=dict(reversed(list(_failure_vector().items()))),
        safety_gate=dict(reversed(list(_safety_gate().items()))),
        quality_proof_commands=("python -m pytest -q",),
    )

    assert first.decision_id == second.decision_id
    assert first.status == "eligible_for_proposal"
    assert first.primary_blocker == "1 file would be reformatted"
    assert first.owner_surface == "tests/test_widget.py"
    assert first.confidence == "high"
    assert first.focused_proof == ("python -m ruff format --check tests/test_widget.py",)
    assert first.quality_proof == ("make proof-after-format", "python -m pytest -q")
    assert first.authority == {field: False for field in AUTHORITY_FIELDS}
    assert "prepare_patch_proposal" in first.allowed_actions
    assert "mutate_default_branch" in first.blocked_actions
    assert first.proposed_change is None


def test_proposal_ready_is_reviewable_but_never_executable() -> None:
    envelope = build_decision_envelope(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        failure_vector=_failure_vector(),
        safety_gate=_safety_gate(),
        proposal=_proposal(),
        verifier={
            "status": "passed",
            "source_repository": REPOSITORY,
            "source_commit_sha": COMMIT_SHA,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "branch_execution_allowed": False,
            "merge_authorized": False,
            "publication_authorized": False,
            "security_dismissal_allowed": False,
            "semantic_equivalence_proven": False,
        },
    )

    assert envelope.status == "proposal_ready"
    assert envelope.proposed_change == {
        "status": "passed",
        "proposal_status": "eligible_for_human_policy_proposal",
        "proposal_eligible": True,
        "candidate_family": "formatter_only",
        "source_repository": REPOSITORY,
        "source_commit_sha": COMMIT_SHA,
        "source_pr_number": 2141,
        "branch_execution_allowed": False,
    }
    assert "record_authenticated_decision" in envelope.allowed_actions
    assert "execute_on_branch_without_authenticated_approval" in envelope.blocked_actions
    assert envelope.next_human_action == (
        "review the exact-head proposal and record an authenticated decision"
    )
    assert envelope.verifier_state == "passed"


def test_unknown_failure_remains_review_first() -> None:
    envelope = build_decision_envelope(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        failure_vector={"failure_class": "unknown", "risk": "unknown"},
        safety_gate={
            "failure_kind": "unknown",
            "review_first": True,
            "safe_fix_allowed": False,
            "recommended_next_human_action": "triage manually",
        },
    )

    assert envelope.status == "review_required"
    assert envelope.owner_surface == "unknown"
    assert envelope.confidence == "low"
    assert envelope.allowed_actions == ("inspect_evidence",)
    assert envelope.next_human_action == "triage manually"


@pytest.mark.parametrize(
    ("source", "unsafe_payload"),
    [
        ("safety_gate", {"automation_allowed": True}),
        (
            "proposal",
            {
                "source_repository": REPOSITORY,
                "source_commit_sha": COMMIT_SHA,
                "authority_boundary": {"patch_application_allowed": True},
            },
        ),
        (
            "verifier",
            {
                "source_repository": REPOSITORY,
                "source_commit_sha": COMMIT_SHA,
                "decision": {"semantic_equivalence_claim": True},
            },
        ),
    ],
)
def test_rejects_any_authority_expansion(
    source: str,
    unsafe_payload: dict[str, object],
) -> None:
    kwargs: dict[str, object] = {
        "repository": REPOSITORY,
        "commit_sha": COMMIT_SHA,
        "failure_vector": _failure_vector(),
        "safety_gate": _safety_gate(),
    }
    kwargs[source] = unsafe_payload

    with pytest.raises(ValueError, match="expands authority"):
        build_decision_envelope(**kwargs)  # type: ignore[arg-type]


def test_rejects_invalid_identity_and_digest_inputs() -> None:
    with pytest.raises(ValueError, match="owner/name"):
        build_decision_envelope(
            repository="invalid",
            commit_sha=COMMIT_SHA,
            failure_vector=_failure_vector(),
            safety_gate=_safety_gate(),
        )
    with pytest.raises(ValueError, match="40- or 64-character"):
        build_decision_envelope(
            repository=REPOSITORY,
            commit_sha="ABC",
            failure_vector=_failure_vector(),
            safety_gate=_safety_gate(),
        )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        build_decision_envelope(
            repository=REPOSITORY,
            commit_sha=COMMIT_SHA,
            failure_vector=_failure_vector(),
            safety_gate=_safety_gate(),
            evidence_digests={"external": "not-a-digest"},
        )


def test_json_and_markdown_outputs_are_deterministic_and_defensive(tmp_path: Path) -> None:
    envelope = build_decision_envelope(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        failure_vector=_failure_vector(),
        safety_gate=_safety_gate(),
        proposal=_proposal(),
    )
    decision_id = envelope.decision_id
    failure_digest = envelope.evidence_digests["failure_vector"]

    exposed_failure = envelope.failure_vector
    exposed_authority = envelope.authority
    exposed_proposal = envelope.proposed_change
    exposed_digests = envelope.evidence_digests
    exposed_failure["failure_class"] = "mutated"
    exposed_authority["merge_authorized"] = True
    assert exposed_proposal is not None
    exposed_proposal["proposal_status"] = "mutated"
    exposed_digests["failure_vector"] = "f" * 64

    assert envelope.decision_id == decision_id
    assert envelope.failure_vector["failure_class"] == "formatter_only"
    assert envelope.authority == {field: False for field in AUTHORITY_FIELDS}
    assert envelope.proposed_change is not None
    assert envelope.proposed_change["proposal_status"] == "eligible_for_human_policy_proposal"
    assert envelope.evidence_digests["failure_vector"] == failure_digest

    output = tmp_path / "decision-envelope.json"
    write_decision_envelope(envelope, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    markdown = render_decision_envelope_markdown(envelope)

    assert payload["schema_version"] == "sdetkit.decision_envelope.v2"
    assert payload["decision_id"] == decision_id
    assert payload["failure_vector"]["failure_class"] == "formatter_only"
    assert payload["authority"] == {field: False for field in AUTHORITY_FIELDS}
    assert payload["evidence_digests"]["failure_vector"] == failure_digest
    assert payload["evidence_digests"] == dict(sorted(payload["evidence_digests"].items()))
    assert "# SDETKit Decision Envelope" in markdown
    assert "- branch_execution_allowed: `false`" in markdown
    assert markdown.endswith("\n")

    payload["failure_vector"]["failure_class"] = "mutated_again"
    assert envelope.failure_vector["failure_class"] == "formatter_only"


def test_rejects_stale_or_cross_repository_proposal_evidence() -> None:
    stale = _proposal()
    stale["source_commit_sha"] = "b" * 40
    with pytest.raises(ValueError, match="decision head"):
        build_decision_envelope(
            repository=REPOSITORY,
            commit_sha=COMMIT_SHA,
            failure_vector=_failure_vector(),
            safety_gate=_safety_gate(),
            proposal=stale,
        )

    cross_repo = _proposal()
    cross_repo["source_repository"] = "someone/else"
    with pytest.raises(ValueError, match="decision repository"):
        build_decision_envelope(
            repository=REPOSITORY,
            commit_sha=COMMIT_SHA,
            failure_vector=_failure_vector(),
            safety_gate=_safety_gate(),
            proposal=cross_repo,
        )


def test_computed_evidence_digests_cannot_be_overridden() -> None:
    with pytest.raises(ValueError, match="computed and cannot be overridden"):
        build_decision_envelope(
            repository=REPOSITORY,
            commit_sha=COMMIT_SHA,
            failure_vector=_failure_vector(),
            safety_gate=_safety_gate(),
            evidence_digests={"failure_vector": "f" * 64},
        )


def test_decision_envelope_contract_keeps_all_authority_false() -> None:
    contract = json.loads(
        Path("docs/contracts/decision-envelope.v2.json").read_text(encoding="utf-8")
    )

    assert contract["schema_version"] == "sdetkit.decision_envelope_contract.v2"
    assert contract["payload_schema_version"] == "sdetkit.decision_envelope.v2"
    assert contract["required_fields"] == [
        "decision_id",
        "repository",
        "commit_sha",
        "status",
        "primary_blocker",
        "failure_vector",
        "owner_surface",
        "confidence",
        "risk",
        "authority",
        "allowed_actions",
        "blocked_actions",
        "proposed_change",
        "focused_proof",
        "quality_proof",
        "verifier_state",
        "next_human_action",
        "evidence_digests",
    ]
    assert contract["rules"]["bound_payloads_are_defensive_copies"] is True
    assert set(contract["authority_boundary"]) == set(AUTHORITY_FIELDS)
    assert all(value is False for value in contract["authority_boundary"].values())
