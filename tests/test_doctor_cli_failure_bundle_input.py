from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor

UNKNOWN_REVIEW_REQUIRED = "UNKNOWN" + "_REVIEW" + "_REQUIRED"


def _write_failure_bundle(path: Path, *, clear: bool = False) -> Path:
    operator_brief = path.parent / "operator-brief.md"
    operator_brief.write_text("# operator brief\n", encoding="utf-8")
    payload = {
        "schema_version": "sdetkit.adaptive.failure_bundle.v1",
        "status": "clear" if clear else "needs_fix",
        "primary_diagnosis_code": "" if clear else UNKNOWN_REVIEW_REQUIRED,
        "diagnosis_count": 0 if clear else 1,
        "review_first": False if clear else True,
        "safe_to_auto_fix": False,
        "artifacts": {"operator_brief_markdown": operator_brief.as_posix()},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_doctor_diagnose_cli_accepts_failure_bundle(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    bundle = _write_failure_bundle(tmp_path / "failure-intelligence-bundle.json")
    out_path = tmp_path / "doctor-diagnosis.json"

    rc = doctor.main(
        [
            "--diagnose",
            "--failure-bundle",
            str(bundle),
            "--format",
            "json",
            "--out",
            str(out_path),
            "--no-workspace",
        ]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    ids = {item["diagnosis_id"] for item in payload["diagnoses"]}
    assert "doctor.adaptive_failure_bundle" in ids


def test_doctor_diagnose_cli_clear_failure_bundle_stays_quiet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    bundle = _write_failure_bundle(tmp_path / "failure-intelligence-bundle.json", clear=True)
    out_path = tmp_path / "doctor-diagnosis.json"

    rc = doctor.main(
        [
            "--diagnose",
            f"--failure-bundle={bundle}",
            "--format",
            "json",
            "--out",
            str(out_path),
            "--no-workspace",
        ]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    ids = {item["diagnosis_id"] for item in payload["diagnoses"]}
    assert "doctor.adaptive_failure_bundle" not in ids


def test_doctor_prescribe_cli_accepts_failure_bundle(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    bundle = _write_failure_bundle(tmp_path / "failure-intelligence-bundle.json")
    out_path = tmp_path / "doctor-prescriptions.json"

    rc = doctor.main(
        [
            "--prescribe",
            "--failure-bundle",
            str(bundle),
            "--format",
            "json",
            "--out",
            str(out_path),
            "--no-workspace",
        ]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["prescription_count"] >= 1
