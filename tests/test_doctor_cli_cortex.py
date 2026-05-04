import json

import pytest

from sdetkit import doctor


def test_doctor_diagnose_writes_diagnosis_contract(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out_path = tmp_path / "doctor-diagnosis.json"

    rc = doctor.main(["--diagnose", "--format", "json", "--out", str(out_path)])

    assert rc == 0
    assert capsys.readouterr().out == ""

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.doctor.diagnosis.v1"
    assert payload["source"]["output_path"] == "[REDACTED]"
    assert "diagnoses" in payload


def test_doctor_prescribe_writes_prescription_contract(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out_path = tmp_path / "doctor-prescriptions.json"

    rc = doctor.main(["--prescribe", "--format", "json", "--out", str(out_path)])

    assert rc == 0
    assert capsys.readouterr().out == ""

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.doctor.prescriptions.v1"
    assert payload["source_schema_version"] == "sdetkit.doctor.diagnosis.v1"
    assert payload["source"]["source_output_path"] == "[REDACTED]"
    assert payload["prescriptions"] == []
    assert payload["next_commands"] == []
    assert payload["verification_commands"] == []


def test_doctor_prescribe_text_stdout_is_summary_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--prescribe", "--format", "text"])

    assert rc == 0

    output = capsys.readouterr().out

    assert "schema_version=sdetkit.doctor.prescriptions.v1" in output
    assert "prescription_count=" in output
    assert "prescription=doctor." not in output


def test_doctor_cortex_flags_are_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        doctor.main(["--diagnose", "--prescribe"])

    assert exc.value.code == 2


def test_doctor_cortex_rejects_markdown_format():
    with pytest.raises(SystemExit) as exc:
        doctor.main(["--diagnose", "--format", "md"])

    assert exc.value.code == 2
