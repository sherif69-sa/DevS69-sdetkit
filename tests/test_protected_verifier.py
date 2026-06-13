from __future__ import annotations

import json
from pathlib import Path

from sdetkit.patch_scorer import score_patch
from sdetkit.protected_verifier import main, render_markdown, verify_patch

_key = "_".join
CANDIDATE_FOR_PROTECTED_VERIFICATION = _key(("candidate", "for", "protected", "verification"))
REVIEW_REQUIRED = _key(("review", "required"))
BLOCKED_REVIEW_FIRST = _key(("blocked", "review", "first"))
HUMAN_REVIEW_REQUIRED_BEFORE_PATCH_APPLICATION = _key(
    ("human", "review", "required", "before", "patch", "application")
)


def _safe_plan() -> dict:
    return {
        "plans": [
            {
                "diagnosis_id": "formatting-autopilot",
                "failure_surface": "formatting",
                "classification": "formatting_only",
                "safe_to_auto_fix": True,
                "allowed_strategy": "run_pre_commit",
                "blocked_reason": "",
                "risk_level": "low",
                "affected_files": ["src/sdetkit/example.py"],
                "exact_fix_scope": {
                    "allowed_files": ["src/sdetkit/example.py"],
                    "allowed_strategy": "run_pre_commit",
                    "scope": "deterministic formatting or whitespace only",
                },
                "proof_commands": ["python -m pre_commit run -a"],
            }
        ]
    }


def _safe_insights() -> dict:
    return {
        "recurring_review_first_surfaces": [],
        "recurring_safe_fix_patterns": [
            {
                "failure_class": "formatting_only",
                "action": "run_pre_commit",
                "count": 2,
            }
        ],
        "safety_gate_evidence": {
            "collection_status": "collected",
            "status": "safety_gate_evidence_observed",
            "source": "trajectory.safety_gate",
            "record_count": 1,
            "safe_fix_allowed_count": 1,
            "review_first_count": 0,
            "reporting_only_count": 1,
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    }


def _candidate_patch_score() -> dict:
    return score_patch(
        remediation_plan=_safe_plan(),
        proposed_patch={
            "patch_id": "format-patch",
            "changed_files": ["src/sdetkit/example.py"],
        },
        pattern_insights=_safe_insights(),
    )


def _repo_memory_profile() -> dict:
    return {
        "schema_version": "sdetkit.repo_memory.v6",
        "profile_status": "observation_only",
        "failure_vector_contract_evidence": {
            "collection_status": "collected",
            "status": "failure_vector_contract_evidence_observed",
            "source": "trajectory.failure_vector_contract",
            "record_count": 1,
            "security_relevance_count": 0,
            "authority_boundary_preserved_count": 1,
            "failure_kinds": [{"value": "formatter_only", "count": 1}],
            "affected_surfaces": [{"value": "source", "count": 1}],
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "security_dismissal_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_claim": False,
            },
        },
    }


def test_protected_verifier_keeps_candidate_review_first_without_authority() -> None:
    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        failure_bundle={
            "status": "collected",
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
        runtime_proof={
            "status": "collected",
            "decision_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
    )

    assert payload["schema_version"] == "sdetkit.protected_verifier.decision.v1"
    assert payload["decision"]["status"] == REVIEW_REQUIRED
    assert payload["decision"]["review_first"] is True
    assert payload["decision"][CANDIDATE_FOR_PROTECTED_VERIFICATION] is True
    assert payload["decision"]["protected_verification_passed"] is False
    assert payload["decision"]["automation_allowed"] is False
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert payload["decision"]["next_action"] == HUMAN_REVIEW_REQUIRED_BEFORE_PATCH_APPLICATION
    assert payload["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }
    assert payload["verification_evidence"]["proof_requirements"] == ["python -m pre_commit run -a"]
    assert payload["risk_flags"] == []

    markdown = render_markdown(payload)
    assert "# ProtectedVerifier decision" in markdown
    assert "Review first: `true`" in markdown
    assert "Protected verification passed: `false`" in markdown
    assert "Patch application allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def test_protected_verifier_blocks_non_candidate_patch_score() -> None:
    patch_score = _candidate_patch_score()
    patch_score["decision"]["status"] = BLOCKED_REVIEW_FIRST
    patch_score["decision"][CANDIDATE_FOR_PROTECTED_VERIFICATION] = False

    payload = verify_patch(patch_score=patch_score)

    assert payload["decision"]["status"] == BLOCKED_REVIEW_FIRST
    assert payload["decision"][CANDIDATE_FOR_PROTECTED_VERIFICATION] is False
    assert payload["decision"]["automation_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert any(
        flag["code"] == "PATCH_SCORE_NOT_CANDIDATE" and flag["blocking"] is True
        for flag in payload["risk_flags"]
    )


def test_protected_verifier_blocks_authority_expansion_attempts() -> None:
    patch_score = _candidate_patch_score()
    patch_score["decision"]["merge_authorized"] = True

    payload = verify_patch(
        patch_score=patch_score,
        runtime_proof={
            "status": "collected",
            "decision_boundary": {"semantic_equivalence_proven": True},
        },
    )

    assert payload["decision"]["status"] == BLOCKED_REVIEW_FIRST
    assert payload["decision"]["automation_allowed"] is False
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert {
        field
        for flag in payload["risk_flags"]
        if flag["code"] == "AUTHORITY_EXPANSION_ATTEMPT"
        for field in flag["fields"]
    } == {"merge_authorized", "semantic_equivalence_proven"}


def test_protected_verifier_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    patch_score_path = tmp_path / "patch-score.json"
    out_dir = tmp_path / "protected-verifier"
    patch_score_path.write_text(json.dumps(_candidate_patch_score()), encoding="utf-8")

    rc = main(
        [
            "--patch-score",
            str(patch_score_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    payload = json.loads((out_dir / "protected-verifier-decision.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "protected-verifier-decision.md").read_text(encoding="utf-8")

    assert printed["schema_version"] == "sdetkit.protected_verifier.decision.v1"
    assert printed["decision"]["status"] == REVIEW_REQUIRED
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert "# ProtectedVerifier decision" in markdown
    assert "This verifier is reporting-only" in markdown


def test_protected_verifier_consumes_repo_memory_failure_vector_contract_evidence() -> None:
    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        repo_memory_profile=_repo_memory_profile(),
    )

    evidence = payload["repo_memory_evidence"]["failure_vector_contract_evidence"]
    assert evidence["collection_status"] == "collected"
    assert evidence["status"] == "failure_vector_contract_evidence_observed"
    assert evidence["record_count"] == 1
    assert evidence["security_relevance_count"] == 0
    assert evidence["authority_boundary_preserved_count"] == 1
    assert evidence["failure_kinds"] == [{"value": "formatter_only", "count": 1}]
    assert evidence["affected_surfaces"] == [{"value": "source", "count": 1}]
    assert evidence["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }
    assert payload["decision"]["status"] == REVIEW_REQUIRED
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert payload["risk_flags"] == []

    markdown = render_markdown(payload)
    assert "## RepoMemory FailureVector contract evidence" in markdown
    assert "Authority boundary preserved records: `1`" in markdown
    assert (
        "Security dismissal allowed by RepoMemory FailureVector contract evidence: `false`"
        in markdown
    )
    assert (
        "Semantic equivalence claimed by RepoMemory FailureVector contract evidence: `false`"
        in markdown
    )


def test_protected_verifier_blocks_authority_expanding_repo_memory_contract_evidence() -> None:
    profile = _repo_memory_profile()
    profile["failure_vector_contract_evidence"]["decision_boundary"]["merge_authorized"] = True

    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        repo_memory_profile=profile,
    )

    assert payload["decision"]["status"] == BLOCKED_REVIEW_FIRST
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert any(
        flag["code"] == "FAILURE_VECTOR_CONTRACT_EVIDENCE_AUTHORITY_VIOLATION"
        and flag["blocking"] is True
        and flag["fields"] == ["merge_authorized"]
        for flag in payload["risk_flags"]
    )


def _runtime_proof_with_protected_verifier_contract() -> dict:
    return {
        "schema_version": "sdetkit.pr_quality_runtime_proof_artifacts.v1",
        "status": "collected",
        "protected_verifier": {
            "collection_status": "collected",
            "status": "review_required",
            "review_first": True,
            "contract_status": "failure_vector_contract_evidence_observed",
            "contract_record_count": 1,
            "contract_security_relevance_count": 0,
            "contract_authority_boundary_preserved_count": 1,
            "contract_patch_application_allowed": False,
            "contract_security_dismissal_allowed": False,
            "contract_merge_authorized": False,
            "contract_semantic_equivalence_claim": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def test_protected_verifier_consumes_runtime_proof_protected_verifier_contract_evidence() -> None:
    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        runtime_proof=_runtime_proof_with_protected_verifier_contract(),
    )

    evidence = payload["runtime_proof_evidence"]["protected_verifier_contract_evidence"]
    assert evidence["collection_status"] == "collected"
    assert evidence["status"] == "failure_vector_contract_evidence_observed"
    assert evidence["source"] == "runtime_proof.protected_verifier.failure_vector_contract_evidence"
    assert evidence["record_count"] == 1
    assert evidence["security_relevance_count"] == 0
    assert evidence["authority_boundary_preserved_count"] == 1
    assert evidence["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }
    assert payload["decision"]["status"] == REVIEW_REQUIRED
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert payload["risk_flags"] == []

    markdown = render_markdown(payload)
    assert "## Runtime proof ProtectedVerifier contract evidence" in markdown
    assert "Authority boundary preserved records: `1`" in markdown
    assert (
        "Patch application allowed by runtime proof ProtectedVerifier contract evidence: `false`"
        in markdown
    )
    assert (
        "Security dismissal allowed by runtime proof ProtectedVerifier contract evidence: `false`"
        in markdown
    )
    assert (
        "Merge authorized by runtime proof ProtectedVerifier contract evidence: `false`" in markdown
    )
    assert (
        "Semantic equivalence claimed by runtime proof ProtectedVerifier contract evidence: `false`"
        in markdown
    )


def test_protected_verifier_blocks_authority_expanding_runtime_proof_contract_evidence() -> None:
    runtime = _runtime_proof_with_protected_verifier_contract()
    runtime["protected_verifier"]["contract_patch_application_allowed"] = True
    runtime["protected_verifier"]["contract_semantic_equivalence_claim"] = True

    payload = verify_patch(
        patch_score=_candidate_patch_score(),
        runtime_proof=runtime,
    )

    assert payload["decision"]["status"] == BLOCKED_REVIEW_FIRST
    assert payload["decision"]["patch_application_allowed"] is False
    assert payload["decision"]["merge_authorized"] is False
    assert payload["decision"]["semantic_equivalence_proven"] is False
    assert any(
        flag["code"] == "RUNTIME_PROOF_PROTECTED_VERIFIER_CONTRACT_AUTHORITY_VIOLATION"
        and flag["blocking"] is True
        and flag["fields"] == ["patch_application_allowed", "semantic_equivalence_claim"]
        for flag in payload["risk_flags"]
    )
