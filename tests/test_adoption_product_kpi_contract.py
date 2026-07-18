from __future__ import annotations

import json
from pathlib import Path


CONTRACT_PATH = Path("docs/contracts/adoption-product-kpi-evidence.v1.json")
EXPECTED_METRICS = {
    "discovery_precision",
    "first_failure_extraction_precision",
    "workspace_ownership_precision",
    "proof_command_actionability",
    "authority_boundary_preservation",
    "unsafe_authority_rejection",
    "operator_actionability",
}
EXPECTED_OUTCOMES = {
    "pass",
    "fail",
    "unavailable",
    "malformed",
    "unsupported",
    "not_applicable",
}
REQUIRED_PROVENANCE_FIELDS = {
    "observation_id",
    "repository_name",
    "repository_url",
    "source_commit_sha",
    "evidence_path",
    "evidence_sha256",
    "reviewer_id",
    "reviewed_at",
    "metric_outcomes",
    "review_notes",
}
AUTHORITY_FIELDS = {
    "automation_allowed",
    "merge_authorized",
    "patch_application_allowed",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
}


def _contract() -> dict[str, object]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_adoption_product_kpi_contract_defines_reviewed_metrics_and_denominators() -> None:
    payload = _contract()

    assert payload["schema_version"] == "sdetkit.adoption_product_kpi_evidence.v1"
    assert set(payload["allowed_observation_outcomes"]) == EXPECTED_OUTCOMES
    assert set(payload["required_observation_fields"]) == REQUIRED_PROVENANCE_FIELDS

    definitions = payload["metric_definitions"]
    assert isinstance(definitions, list)
    assert {definition["metric_id"] for definition in definitions} == EXPECTED_METRICS
    for definition in definitions:
        assert definition["numerator"] == "reviewed_pass_observations"
        assert definition["denominator"] == "reviewed_applicable_observations"
        assert str(definition["description"]).strip()


def test_adoption_product_kpi_contract_preserves_review_first_authority() -> None:
    payload = _contract()
    authority = payload["authority_boundary"]
    rules = payload["rules"]

    assert set(authority) == AUTHORITY_FIELDS
    assert all(authority[field] is False for field in AUTHORITY_FIELDS)
    assert rules["reviewed_observations_only"] is True
    assert rules["source_provenance_required"] is True
    assert rules["explicit_denominators_required"] is True
    assert rules["unavailable_malformed_unsupported_retained"] is True
    assert rules["predictions_are_proof"] is False
    assert rules["missing_outcomes_inferred"] is False
    assert rules["authoritative_zero_after_collection_failure"] is False
    assert rules["target_repo_mutation"] is False
    assert rules["target_tests_executed_by_reporter"] is False


def test_adoption_product_kpi_contract_requires_report_provenance_and_outcome_totals() -> None:
    payload = _contract()

    required_report_fields = set(payload["required_report_fields"])
    assert {
        "input_provenance",
        "reviewed_observation_count",
        "metrics",
        "outcome_totals",
        "authority_boundary",
        "rules",
    } <= required_report_fields
