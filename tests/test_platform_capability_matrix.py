from __future__ import annotations

import json
from pathlib import Path

MATRIX_PATH = Path("docs/contracts/platform-capability-matrix.v1.json")
ROADMAP_PATH = Path("docs/roadmap/product-roadmap.md")
FAILURE_VECTOR_MATRIX_PATH = Path("docs/contracts/failure-vector-support-matrix.v1.json")
SAFETY_GATE_MATRIX_PATH = Path("docs/contracts/safety-gate-policy-matrix.v1.json")

EXPECTED_CAPABILITIES = {
    "failure_vector_engine",
    "safety_gate",
    "trajectory_store",
    "repo_memory",
    "replayable_benchmark_harness",
    "protected_verifier",
    "patch_scorer",
    "pr_reporting",
    "local_diagnostic_queue",
    "merge_readiness",
    "azure_devops_proof_discovery",
    "circleci_proof_discovery",
    "cpp_proof_surface_discovery",
    "cpp_saved_failure_normalization",
    "cpp_quality_security_evidence",
    "cpp_complete_operator_proof",
    "multi_ecosystem_adoption",
    "mixed_monorepo_operator_proof",
    "reviewed_repository_kpi_evidence",
    "product_maturity_kpi_portfolio_projection",
    "remediation_research_contract",
    "formatter_policy_proposal_eligibility",
}

AUTHORITY_FIELDS = {
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "publication_authorized",
    "merge_authorized",
    "semantic_equivalence_proven",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_platform_capability_matrix_matches_current_repo_owners() -> None:
    payload = _load(MATRIX_PATH)

    assert payload["schema_version"] == "sdetkit.platform_capability_matrix.v1"
    assert payload["product_stage"] == "local_first_reliability_platform"

    rows = payload["capabilities"]
    assert {row["capability_id"] for row in rows} == EXPECTED_CAPABILITIES
    assert all(row["status"] == "implemented_and_tested" for row in rows)

    for row in rows:
        assert row["title"]
        assert row["authority"]
        assert row["owner_files"]
        assert row["proof_tests"]
        for owner_path in row["owner_files"]:
            assert Path(owner_path).exists(), owner_path
        for proof_path in row["proof_tests"]:
            assert Path(proof_path).is_file(), proof_path


def test_platform_capability_matrix_separates_gaps_from_closed_blockers() -> None:
    payload = _load(MATRIX_PATH)

    gaps = {row["gap_id"]: row for row in payload["active_repository_gaps"]}
    assert {"formatter_policy_proposal_observation"} == set(gaps)
    assert "azure_devops_proof_discovery" not in gaps
    assert "real_repository_kpi_evidence" not in gaps
    assert all(row["review_first"] is True for row in gaps.values())
    assert all(row["priority"] in {"P1", "P2", "P3"} for row in gaps.values())
    assert all(row["exit_criteria"] for row in gaps.values())

    capability_ids = {row["capability_id"] for row in payload["capabilities"]}
    assert "azure_devops_proof_discovery" in capability_ids
    assert "reviewed_repository_kpi_evidence" in capability_ids
    assert "product_maturity_kpi_portfolio_projection" in capability_ids
    assert "remediation_research_contract" in capability_ids
    assert "formatter_policy_proposal_eligibility" in capability_ids
    assert payload["external_or_manual_blockers"] == []


def test_platform_capability_matrix_preserves_denied_authority() -> None:
    payload = _load(MATRIX_PATH)
    authority = payload["authority_boundary"]

    assert set(authority) == AUTHORITY_FIELDS
    assert all(value is False for value in authority.values())

    blocked = set(payload["intentionally_blocked"])
    assert "broad automatic patch application" in blocked
    assert "automatic security remediation or dismissal" in blocked
    assert "automatic release publication" in blocked
    assert "automatic merge authorization" in blocked


def test_completed_platform_layers_are_not_relisted_as_future_waves() -> None:
    completed_titles = {
        "SafetyGate policy expansion",
        "TrajectoryStore / RepoMemory expansion",
        "ReplayableBenchmarkHarness",
        "ProtectedVerifier",
        "PRReporter",
        "JobQueue",
    }

    for path in (FAILURE_VECTOR_MATRIX_PATH, SAFETY_GATE_MATRIX_PATH):
        payload = _load(path)
        blocked = {item["item"] for item in payload["blocked_until_future_wave"]}
        assert completed_titles.isdisjoint(blocked)


def test_product_roadmap_uses_current_capability_portfolio_and_ladder() -> None:
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")

    assert "docs/contracts/platform-capability-matrix.v1.json" in roadmap
    assert "CircleCI proof-command discovery" in roadmap
    assert "Azure DevOps proof-command discovery" in roadmap
    assert "mixed-language monorepo operator vertical" in roadmap
    assert "reviewed real-repository product KPI evidence" in roadmap
    assert "The reviewed real-repository KPI baseline is complete." in roadmap
    assert "adoption-product-kpi-report.json" in roadmap
    assert "two reviewed observations" in roadmap
    assert "eleven reviewed pass outcomes" in roadmap
    assert "`formatter_policy_proposal_observation`" in roadmap
    assert "Formatter policy proposal eligibility" in roadmap
    assert "docs/contracts/remediation-research.v1.json" in roadmap
    assert "The versioned remediation-research contract is implemented and tested." in roadmap
    assert "Candidate benchmark: formatter-only" in roadmap
    assert "expand reviewed KPI denominators" not in roadmap
    assert "The `v1.2.0` publication gate is complete." in roadmap
    assert "external configuration required" not in roadmap

    for completed_issue in ("#1937", "#1946", "#2045", "#1945"):
        assert completed_issue not in roadmap
