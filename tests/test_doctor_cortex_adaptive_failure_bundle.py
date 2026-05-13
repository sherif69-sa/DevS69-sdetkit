from __future__ import annotations

from sdetkit import doctor_diagnosis, doctor_prescriptions

UNKNOWN_REVIEW_REQUIRED = "UNKNOWN" + "_REVIEW" + "_REQUIRED"


def _source_with_failure_bundle() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.doctor.v2",
        "ok": True,
        "checks": {},
        "summary": {"failed": 0},
        "adaptive_failure_bundle": {
            "enabled": True,
            "ok": False,
            "schema_version": "sdetkit.adaptive.failure_bundle.v1",
            "status": "needs_fix",
            "primary_diagnosis_code": UNKNOWN_REVIEW_REQUIRED,
            "diagnosis_count": 1,
            "review_first": True,
            "safe_to_auto_fix": False,
            "operator_brief_markdown": "build/sdetkit/failure-intelligence/operator-brief.md",
        },
    }


def test_doctor_diagnosis_includes_adaptive_failure_bundle_signal() -> None:
    payload = doctor_diagnosis.build_diagnosis_payload(_source_with_failure_bundle())

    assert payload["ok"] is False
    assert payload["diagnosis_count"] == 1
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["diagnosis_id"] == "doctor.adaptive_failure_bundle"
    assert diagnosis["category"] == "adaptive_failure_bundle"
    assert diagnosis["severity"] == "high"
    assert UNKNOWN_REVIEW_REQUIRED in diagnosis["summary"]
    assert "review_first=true" in diagnosis["summary"]
    assert "safe_to_auto_fix=false" in diagnosis["summary"]


def test_clear_adaptive_failure_bundle_does_not_create_doctor_finding() -> None:
    source = _source_with_failure_bundle()
    bundle = source["adaptive_failure_bundle"]
    assert isinstance(bundle, dict)
    bundle.update(
        {
            "ok": True,
            "status": "clear",
            "primary_diagnosis_code": "",
            "diagnosis_count": 0,
            "review_first": False,
            "safe_to_auto_fix": False,
        }
    )

    payload = doctor_diagnosis.build_diagnosis_payload(source)

    assert payload["ok"] is True
    assert payload["diagnosis_count"] == 0


def test_doctor_prescriptions_has_adaptive_failure_bundle_guidance() -> None:
    diagnosis_payload = {
        "schema_version": "sdetkit.doctor.diagnosis.v1",
        "ok": False,
        "status": "fail",
        "diagnoses": [
            {
                "diagnosis_id": "doctor.adaptive_failure_bundle",
                "category": "adaptive_failure_bundle",
                "status": "fail",
                "severity": "high",
                "summary": "Adaptive failure bundle requires review.",
            }
        ],
    }

    payload = doctor_prescriptions.build_prescription_payload(diagnosis_payload)

    assert payload["ok"] is False
    assert payload["prescription_count"] == 1
    prescription = payload["prescriptions"][0]
    assert prescription["diagnosis_id"] == "doctor.adaptive_failure_bundle"
    assert "review_adaptive_failure_bundle" in prescription["prescription_id"]
    assert "adaptive failure bundle" in prescription["summary"].lower()
    assert "not permission to auto-fix" in prescription["why"]
