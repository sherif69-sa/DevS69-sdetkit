from __future__ import annotations

import pytest

from tools.release_readiness_doctor import (
    MALFORMED_DOCTOR_REASON,
    evaluate_doctor_evidence,
)


def test_current_doctor_v2_mapping_is_healthy_evidence() -> None:
    result = evaluate_doctor_evidence(
        {
            "schema_version": "sdetkit.doctor.v2",
            "ok": True,
            "score": 100,
            "quality": {"failed_checks": 0},
            "checks": {
                "pyproject": {"ok": True},
                "release_meta": {"ok": True},
            },
        }
    )

    assert result == {
        "status": "green",
        "evidence_available": True,
        "failing_checks": [],
        "actionable_reasons": [],
    }


def test_current_doctor_v2_mapping_reports_sorted_failing_ids() -> None:
    result = evaluate_doctor_evidence(
        {
            "schema_version": "sdetkit.doctor.v2",
            "ok": False,
            "summary": {"failed": 2},
            "checks": {
                "release_meta": {"ok": False},
                "pyproject": {"passed": True},
                "ci_workflows": {"passed": False},
            },
        }
    )

    assert result["status"] == "blocked"
    assert result["evidence_available"] is True
    assert result["failing_checks"] == ["ci_workflows", "release_meta"]
    assert result["actionable_reasons"] == ["failing doctor checks: 2"]
    assert isinstance(result["status"], str)


def test_legacy_list_checks_remain_supported_without_invented_ids() -> None:
    result = evaluate_doctor_evidence(
        {
            "schema_version": "sdetkit.doctor.v1",
            "quality": {"failed_checks": 2},
            "checks": [
                {"name": "deps", "ok": False},
                {"id": "ci_workflows", "passed": True},
                {"ok": False},
            ],
        }
    )

    assert result["status"] == "review_required"
    assert result["evidence_available"] is True
    assert result["failing_checks"] == ["deps"]
    assert result["actionable_reasons"] == ["failing doctor checks: 1"]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"raw": "not-json"},
        {"schema_version": "sdetkit.doctor.v2", "checks": []},
        {"schema_version": "sdetkit.doctor.v99", "checks": {}},
        {"schema_version": "sdetkit.doctor.v1", "checks": {}},
    ],
)
def test_malformed_or_unknown_doctor_evidence_stays_actionable(payload: object) -> None:
    assert evaluate_doctor_evidence(payload) == {
        "status": "unknown",
        "evidence_available": False,
        "failing_checks": [],
        "actionable_reasons": [MALFORMED_DOCTOR_REASON],
    }


def test_explicit_scalar_status_is_preserved() -> None:
    result = evaluate_doctor_evidence(
        {
            "schema_version": "sdetkit.doctor.v2",
            "status": "review_required",
            "summary": {"nested": "object"},
            "checks": {},
        }
    )

    assert result["status"] == "review_required"
    assert isinstance(result["status"], str)
