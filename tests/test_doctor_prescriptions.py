import json

from sdetkit import doctor_prescriptions


def _clean_diagnosis_payload():
    return {
        "schema_version": "sdetkit.doctor.diagnosis.v1",
        "ok": True,
        "status": "pass",
        "severity": "low",
        "confidence": 0.94,
        "diagnosis_count": 0,
        "diagnoses": [],
    }


def _failed_diagnosis_payload():
    return {
        "schema_version": "sdetkit.doctor.diagnosis.v1",
        "ok": False,
        "status": "fail",
        "severity": "high",
        "confidence": 0.82,
        "diagnosis_count": 2,
        "diagnoses": [
            {
                "diagnosis_id": "doctor.deps",
                "category": "dependency",
                "severity": "medium",
                "summary": "raw source summary should not be copied",
                "evidence": ["raw evidence should not appear"],
                "prescriptions": [{"reason": "raw fix should not appear"}],
            },
            {
                "diagnosis_id": "doctor.clean_tree",
                "category": "release",
                "severity": "high",
                "summary": "raw source summary should not be copied",
                "evidence": ["M private/path.py"],
                "next_commands": ["private command should not appear"],
            },
        ],
        "next_commands": ["private command should not appear"],
        "verification_commands": ["private command should not appear"],
    }


def test_clean_diagnosis_payload_has_no_prescriptions():
    payload = doctor_prescriptions.build_prescription_payload(_clean_diagnosis_payload())

    assert payload["schema_version"] == "sdetkit.doctor.prescriptions.v1"
    assert payload["source_schema_version"] == "sdetkit.doctor.diagnosis.v1"
    assert payload["ok"] is True
    assert payload["status"] == "pass"
    assert payload["severity"] == "low"
    assert payload["prescription_count"] == 0
    assert payload["prescriptions"] == []
    assert payload["next_commands"] == []
    assert payload["verification_commands"] == []
    assert payload["source"] == {
        "workflow": "doctor_diagnosis",
        "source_output_path": "[REDACTED]",
    }


def test_failed_diagnoses_create_public_safe_prescriptions():
    payload = doctor_prescriptions.build_prescription_payload(_failed_diagnosis_payload())

    assert payload["ok"] is False
    assert payload["status"] == "action_required"
    assert payload["severity"] == "high"
    assert payload["confidence"] == 0.82
    assert payload["prescription_count"] == 2
    assert payload["severity_counts"]["high"] == 1
    assert payload["severity_counts"]["medium"] == 1

    by_id = {item["diagnosis_id"]: item for item in payload["prescriptions"]}

    assert by_id["doctor.clean_tree"]["priority"] == 85
    assert by_id["doctor.clean_tree"]["category"] == "release"
    assert by_id["doctor.clean_tree"]["safe_to_auto_apply"] is False
    assert by_id["doctor.clean_tree"]["commands"] == []
    assert by_id["doctor.clean_tree"]["verification_commands"] == [
        "python -m sdetkit doctor --clean-tree --format json",
        "python -m sdetkit gate fast",
    ]

    assert by_id["doctor.deps"]["priority"] == 65
    assert by_id["doctor.deps"]["category"] == "dependency"
    assert by_id["doctor.deps"]["summary"] == "Align dependency metadata and test requirements."

    rendered = json.dumps(payload)
    assert "raw source summary should not be copied" not in rendered
    assert "raw evidence should not appear" not in rendered
    assert "raw fix should not appear" not in rendered
    assert "private command should not appear" not in rendered
    assert "M private/path.py" not in rendered


def test_unknown_diagnosis_uses_generic_public_template():
    source = {
        "schema_version": "sdetkit.doctor.diagnosis.v1",
        "diagnoses": [
            {
                "diagnosis_id": "private.custom.finding",
                "category": "private-category",
                "severity": "critical",
                "summary": "do not copy this private text",
            }
        ],
    }

    payload = doctor_prescriptions.build_prescription_payload(source)

    assert payload["prescription_count"] == 1
    item = payload["prescriptions"][0]
    assert item["diagnosis_id"] == "doctor.unknown"
    assert item["category"] == "general"
    assert item["severity"] == "critical"
    assert item["priority"] == 95
    assert item["summary"] == "Review the doctor diagnosis and choose a targeted repair."
    assert "do not copy this private text" not in json.dumps(payload)


def test_cli_writes_json_output(tmp_path, capsys):
    source_path = tmp_path / "diagnosis.json"
    out_path = tmp_path / "prescriptions.json"
    source_path.write_text(json.dumps(_failed_diagnosis_payload()), encoding="utf-8")

    rc = doctor_prescriptions.main(
        ["--source", str(source_path), "--out", str(out_path), "--format", "json"]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.doctor.prescriptions.v1"
    assert payload["prescription_count"] == 2
    assert payload["prescriptions"] == []
    assert payload["next_commands"] == []
    assert payload["verification_commands"] == []
    assert payload["source"]["source_output_path"] == "[REDACTED]"


def test_cli_prints_text_output(tmp_path, capsys):
    source_path = tmp_path / "diagnosis.json"
    source_path.write_text(json.dumps(_failed_diagnosis_payload()), encoding="utf-8")

    rc = doctor_prescriptions.main(["--source", str(source_path), "--format", "text"])

    assert rc == 0

    output = capsys.readouterr().out
    assert "schema_version=sdetkit.doctor.prescriptions.v1" in output
    assert "prescription_count=2" in output
    assert "prescription=doctor.clean_tree" not in output
    assert "raw source summary should not be copied" not in output


def test_cli_rejects_invalid_json(tmp_path, capsys):
    source_path = tmp_path / "invalid.json"
    source_path.write_text("{not json", encoding="utf-8")

    rc = doctor_prescriptions.main(["--source", str(source_path)])

    assert rc == 2
    assert "error=" in capsys.readouterr().err
