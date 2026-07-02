from __future__ import annotations

from sdetkit.pr_quality_adaptive_diagnosis import attach_adaptive_diagnosis


def _model(*, expected: str, observed: str, message: str) -> dict[str, object]:
    return {
        "primary_failure": {
            "available": True,
            "expected": expected,
            "observed": observed,
            "message": message,
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


def test_adaptive_diagnosis_marks_specific_failure_complete() -> None:
    model = _model(
        expected="heavy_workflow_count <= 8",
        observed="heavy_workflow_count = 9",
        message="workflow budget regression",
    )

    attach_adaptive_diagnosis(model)

    card = model["adaptive_diagnosis"]
    assert card["diagnostic_completeness"] == "complete"
    assert card["confidence"] == "high"
    assert card["failure_class"] == "test"
    assert card["owner_files"] == ["tests/test_workflow_contracts.py"]
    assert all(card["checks"].values())
    assert card["review_first"] is True
    assert card["automation_allowed"] is False
    assert card["merge_authorized"] is False


def test_adaptive_diagnosis_exposes_generic_assertion_gaps() -> None:
    model = _model(
        expected="check completes successfully",
        observed="assert False is True",
        message="assert False is True",
    )

    attach_adaptive_diagnosis(model)

    card = model["adaptive_diagnosis"]
    assert card["diagnostic_completeness"] == "partial"
    assert card["checks"]["exact_failure_detail_present"] is False
    assert card["checks"]["expected_observed_specific"] is False
    assert "exact_failure_detail_present" in card["evidence_gaps"]
    assert "expected_observed_specific" in card["evidence_gaps"]


def test_adaptive_diagnosis_keeps_authority_review_first() -> None:
    model = _model(
        expected="heavy_workflow_count <= 8",
        observed="heavy_workflow_count = 9",
        message="workflow budget regression",
    )
    primary = model["primary_failure"]
    primary["automation_allowed"] = True
    primary["provenance_status"] = "unavailable"

    attach_adaptive_diagnosis(model)

    card = model["adaptive_diagnosis"]
    assert card["checks"]["authority_boundary_preserved"] is False
    assert card["checks"]["step_provenance_confirmed"] is False
    assert card["review_first"] is True
    assert card["automation_allowed"] is False
    assert card["patch_application_allowed"] is False
    assert card["merge_authorized"] is False
