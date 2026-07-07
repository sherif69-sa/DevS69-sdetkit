from __future__ import annotations

from pathlib import Path

from sdetkit.doctor_bundle_outputs import (
    doctor_bundle_directory_snapshot,
    doctor_bundle_output_summary,
    expected_doctor_bundle_outputs,
    is_known_doctor_bundle_output,
    missing_doctor_bundle_outputs,
    unknown_doctor_bundle_outputs,
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


def test_unknown_doctor_bundle_outputs_reports_sorted_unknown_names() -> None:
    assert unknown_doctor_bundle_outputs({"z.txt", "doctor-report.json", "a.txt"}) == (
        "a.txt",
        "z.txt",
    )


def test_doctor_bundle_directory_snapshot_only_returns_files(tmp_path: Path) -> None:
    (tmp_path / "doctor-report.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()

    assert doctor_bundle_directory_snapshot(tmp_path) == {"doctor-report.json"}
    assert doctor_bundle_directory_snapshot(tmp_path / "missing") == set()


def test_doctor_bundle_output_summary_is_stable() -> None:
    summary = doctor_bundle_output_summary(
        {"doctor-report.json", "doctor-report.md", "other.json"}
    )

    assert summary == {
        "expected": (
            "doctor-report.json",
            "doctor-report.md",
            "doctor-report-manifest.json",
        ),
        "observed": ("doctor-report.json", "doctor-report.md", "other.json"),
        "missing": ("doctor-report-manifest.json",),
        "unknown": ("other.json",),
        "complete": False,
        "clean": False,
    }
