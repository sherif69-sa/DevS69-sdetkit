from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sdetkit import formatter_policy_proposal

PACKET_ROOT = Path("docs/evidence/formatter-policy-proposal/review-packet-2141")
PROPOSAL = PACKET_ROOT / formatter_policy_proposal.REPORT_JSON
PROPOSAL_MD = PACKET_ROOT / formatter_policy_proposal.REPORT_MD
APPROVAL = PACKET_ROOT / "formatter-policy-approval.json"
VERIFIER_REPORT = PACKET_ROOT / "verifier" / "formatter-candidate-verifier.json"
MANIFEST = PACKET_ROOT / "review-packet-manifest.json"
REVIEW_GUIDE = PACKET_ROOT / "review-checklist.md"
OBSERVATIONS = Path(
    "docs/evidence/formatter-policy-proposal/reviewed-observations.v1.json"
)
SOURCE_REPOSITORY = "sherif69-sa/DevS69-sdetkit"
SOURCE_COMMIT = "2f12fb975c3abab454466dcf7747d5116f8b2a7b"
SOURCE_PR = 2141
AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
)
REVIEW_DIMENSIONS = (
    "exact_evidence_binding",
    "proposal_scope_clarity",
    "proof_plan_actionability",
    "rollback_clarity",
    "authority_boundary_preservation",
    "operator_usefulness",
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_formatter_policy_proposal_review_packet_is_exact_and_non_authorizing() -> None:
    proposal = _load(PROPOSAL)

    assert proposal["schema_version"] == formatter_policy_proposal.SCHEMA_VERSION
    assert proposal["status"] == "passed"
    assert proposal["proposal_status"] == "eligible_for_human_policy_proposal"
    assert proposal["candidate_family"] == "formatter_only"
    assert proposal["source_repository"] == SOURCE_REPOSITORY
    assert proposal["source_commit_sha"] == SOURCE_COMMIT
    assert proposal["source_pr_number"] == SOURCE_PR
    assert proposal["proposal_eligible"] is True
    assert proposal["review_required"] is True
    assert proposal["execution_eligible"] is False
    assert proposal["branch_execution_allowed"] is False
    assert proposal["safe_fix_allowed"] is False
    assert proposal["safety_gate_policy_changed"] is False
    assert all(proposal[field] is False for field in AUTHORITY_FIELDS)


def test_formatter_policy_proposal_review_packet_uses_portable_verifier_paths() -> None:
    verifier_report = _load(VERIFIER_REPORT)
    approval = _load(APPROVAL)
    proposal = _load(PROPOSAL)
    artifacts = verifier_report["artifacts"]

    expected = {
        "controlled_validation": (
            PACKET_ROOT / "verifier" / "formatter-controlled-validation.json"
        ).as_posix(),
        "protected_verifier": (
            PACKET_ROOT / "verifier" / "protected-verifier-result.json"
        ).as_posix(),
        "replay_report": (
            PACKET_ROOT / "verifier" / "formatter-replay-report.json"
        ).as_posix(),
        "repo_memory": (
            PACKET_ROOT / "verifier" / "formatter-repo-memory.json"
        ).as_posix(),
        "trajectory": (
            PACKET_ROOT / "verifier" / "formatter-trajectory.jsonl"
        ).as_posix(),
    }
    assert artifacts == expected
    assert all(Path(path).is_file() for path in artifacts.values())
    assert all("/tmp/" not in path for path in artifacts.values())

    verifier_sha256 = _sha256(VERIFIER_REPORT)
    assert approval["verifier_report_sha256"] == verifier_sha256
    assert proposal["verifier_report_sha256"] == verifier_sha256
    assert proposal["approval_record_sha256"] == _sha256(APPROVAL)


def test_formatter_policy_proposal_review_packet_manifest_binds_every_file() -> None:
    manifest = _load(MANIFEST)

    assert manifest["schema_version"] == (
        "sdetkit.formatter_policy_proposal_review_packet.v1"
    )
    assert manifest["packet_status"] == "ready_for_human_review"
    assert manifest["review_status"] == "pending_human_decision"
    assert manifest["observation_record_created"] is False
    assert manifest["source_repository"] == SOURCE_REPOSITORY
    assert manifest["source_commit_sha"] == SOURCE_COMMIT
    assert manifest["source_pr_number"] == SOURCE_PR
    assert manifest["review_dimensions"] == list(REVIEW_DIMENSIONS)
    assert manifest["allowed_decisions"] == [
        "accept",
        "reject",
        "defer",
        "request_more_evidence",
    ]
    assert manifest["proposal_sha256"] == _sha256(PROPOSAL)
    assert manifest["proposal_markdown_sha256"] == _sha256(PROPOSAL_MD)
    assert manifest["review_checklist_sha256"] == _sha256(REVIEW_GUIDE)
    assert all(
        manifest["authority_boundary"][field] is False for field in AUTHORITY_FIELDS
    )

    retained = {
        path.relative_to(PACKET_ROOT).as_posix(): _sha256(path)
        for path in sorted(PACKET_ROOT.rglob("*"))
        if path.is_file() and path != MANIFEST
    }
    assert manifest["artifact_count"] == len(retained)
    assert manifest["artifact_digests"] == retained
    assert any(path.startswith("benchmark/") for path in retained)
    assert any(path.startswith("verifier/") for path in retained)


def test_formatter_policy_proposal_review_packet_exposes_all_review_dimensions() -> None:
    checklist = REVIEW_GUIDE.read_text(encoding="utf-8")

    assert "pending_human_decision" in checklist
    assert "retained_artifact_paths: `repository_relative`" in checklist
    assert all(dimension in checklist for dimension in REVIEW_DIMENSIONS)
    assert all(
        f"`{decision}`" in checklist
        for decision in ("accept", "reject", "defer", "request_more_evidence")
    )
    assert "does not authorize branch execution" in checklist


def test_formatter_policy_proposal_review_packet_does_not_fabricate_observation() -> None:
    observations = _load(OBSERVATIONS)

    assert observations["schema_version"] == (
        "sdetkit.formatter_policy_proposal_observations.v1"
    )
    assert observations["observations"] == []
