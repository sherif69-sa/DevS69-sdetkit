from __future__ import annotations

from sdetkit.doctor_bundle_outputs import (
    expected_doctor_bundle_outputs,
    is_known_doctor_bundle_output,
    missing_doctor_bundle_outputs,
)


def test_expected_doctor_bundle_outputs_are_deterministic() -> None:
    assert expected_doctor_bundle_outputs() == (
        "doctor-report.json",
        "doctor-report.md",
        "doctor-report-manifest.json",
    )


def test_known_doctor_bundle_outputs_are_limited_to_base_contract() -> None:
    assert is_known_doctor_bundle_output("doctor-report.json") is True
    assert is_known_doctor_bundle_output("doctor-report.md") is True
    assert is_known_doctor_bundle_output("doctor-report-manifest.json") is True
    assert is_known_doctor_bundle_output("other.json") is False


def test_missing_doctor_bundle_outputs_reports_stable_order() -> None:
    assert missing_doctor_bundle_outputs({"doctor-report.json"}) == (
        "doctor-report.md",
        "doctor-report-manifest.json",
    )
