from __future__ import annotations

import json

import pytest

from sdetkit.pr_quality_adaptive_diagnosis import (
    ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION,
    ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION,
    AUTHORITY_EXPECTATIONS,
    adaptive_diagnosis_card,
    attach_adaptive_diagnosis,
    build_export,
    serialize_export,
    validate_authority,
)


def _model() -> dict[str, object]:
    return {
        "primary_failure": {
            "available": True,
            "expected": "heavy_workflow_count <= 8",
            "observed": "heavy_workflow_count = 9",
            "message": "workflow budget regression",
            "test_node": "tests/test_workflow_contracts.py::test_repository_workflow_contracts_pass",
            "reproduction_command": (
                "python -m pytest -q "
                "tests/test_workflow_contracts.py::test_repository_workflow_contracts_pass "
                "-o addopts="
            ),
            "mapping_confidence": "high",
            "provenance_status": "confirmed",
            "step_evidence_status": "confirmed",
            "workflow_exact_head_verified": True,
            "reporting_only": True,
            "families": [{"failure_code": "PYTEST_ASSERTION_FAILURE"}],
        }
    }


def test_export_uses_canonical_adaptive_diagnosis_contract() -> None:
    model = _model()
    attach_adaptive_diagnosis(model)
    card = adaptive_diagnosis_card(model)

    validate_authority(card)
    payload = build_export(card)
    serialized = serialize_export(payload)

    assert payload["schema_version"] == ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION
    assert payload["diagnosis"]["failure_class"] == "test"
    assert payload["authority"] == AUTHORITY_EXPECTATIONS
    assert json.loads(serialized) == payload
    assert serialized.endswith("\n")
    assert ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION.endswith(".v1")


@pytest.mark.parametrize(
    ("field", "expanded_value"),
    [
        ("reporting_only", False),
        ("automation_allowed", True),
        ("patch_application_allowed", True),
        ("security_dismissal_allowed", True),
        ("merge_authorized", True),
        ("semantic_equivalence_proven", True),
    ],
)
def test_authority_validation_rejects_expansion(
    field: str,
    expanded_value: bool,
) -> None:
    card = dict(AUTHORITY_EXPECTATIONS)
    card[field] = expanded_value

    with pytest.raises(ValueError, match="adaptive diagnosis authority"):
        validate_authority(card)
