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
    "multi_ecosystem_adoption",
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


def test_platform_capability_matrix_separates_gaps_and_external_blockers() -> None:
    payload = _load(MATRIX_PATH)

    gaps = {row["gap_id"]: row for row in payload["active_repository_gaps"]}
    assert {
        "circleci_proof_discovery",
        "azure_devops_proof_discovery",
        "mixed_monorepo_vertical",
        "real_repository_kpi_evidence",
        "guarded_remediation_promotion",
    } == set(gaps)
    assert all(row["review_first"] is True for row in gaps.values())
    assert all(row["priority"] in {"P1", "P2", "P3"} for row in gaps.values())
    assert all(row["exit_criteria"] for row in gaps.values())

    blockers = {
        row["blocker_id"]: row for row in payload["external_or_manual_blockers"]
    }
    release = blockers["release_1_1_0_trusted_publishing"]
    assert release["status"] == "external_configuration_required"
    assert "matching PyPI Trusted Publisher verified" in release["required_human_evidence"]
    assert Path("docs/current-product-delta.md") in {
        Path(path) for path in release["owner_files"]
    }


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
    assert "mixed-language monorepo operator vertical" in roadmap
    assert "reviewed real-repository product KPI evidence" in roadmap
    assert "external configuration required" in roadmap

    for completed_issue in ("#1937", "#1946", "#2045", "#1945"):
        assert completed_issue not in roadmap
