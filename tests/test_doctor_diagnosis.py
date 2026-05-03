import json

from sdetkit import doctor_diagnosis


def _clean_payload():
    return {
        "schema_version": "sdetkit.doctor.v2",
        "ok": True,
        "score": 100,
        "checks": {
            "stdlib_shadowing": {
                "ok": True,
                "severity": "high",
                "summary": "no stdlib shadowing detected",
                "evidence": [],
                "fix": [],
            }
        },
        "judgment": {
            "status": "pass",
            "severity": "low",
            "confidence": {"score": 0.94},
            "top_judgment": {"next_move": "No immediate action required."},
        },
        "package": {"name": "sdetkit", "version": "1.0.3"},
        "recommendations": ["Keep CI green."],
    }


def _failed_payload():
    return {
        "schema_version": "sdetkit.doctor.v2",
        "ok": False,
        "score": 72,
        "checks": {
            "deps": {
                "ok": False,
                "severity": "medium",
                "summary": "dependency consistency check failed",
                "evidence": ["requirements-test.txt missing httpx"],
                "fix": ["Install test dependencies with requirements-test.txt."],
            },
            "clean_tree": {
                "ok": False,
                "severity": "high",
                "summary": "working tree has uncommitted changes",
                "evidence": ["M src/sdetkit/doctor.py"],
                "fix": ["Commit or stash changes before release."],
            },
        },
        "judgment": {
            "status": "fail",
            "severity": "high",
            "confidence": {"score": 0.82},
            "top_judgment": {"next_move": "Fix release blockers."},
        },
        "package": {"name": "sdetkit", "version": "1.0.3"},
        "recommendations": ["Fix release blockers."],
    }


def test_build_diagnosis_payload_for_clean_doctor_payload():
    payload = doctor_diagnosis.build_diagnosis_payload(_clean_payload())

    assert payload["schema_version"] == "sdetkit.doctor.diagnosis.v1"
    assert payload["source_schema_version"] == "sdetkit.doctor.v2"
    assert payload["ok"] is True
    assert payload["status"] == "pass"
    assert payload["severity"] == "low"
    assert payload["confidence"] == 0.94
    assert payload["diagnosis_count"] == 0
    assert payload["prescription_count"] == 0
    assert payload["diagnoses"] == []
    assert payload["source"] == {
        "workflow": "doctor",
        "package": "sdetkit",
        "version": "1.0.3",
        "output_path": "",
    }


def test_build_diagnosis_payload_for_failed_checks():
    payload = doctor_diagnosis.build_diagnosis_payload(_failed_payload())

    assert payload["ok"] is False
    assert payload["status"] == "fail"
    assert payload["severity"] == "high"
    assert payload["confidence"] == 0.82
    assert payload["score"] == 72
    assert payload["diagnosis_count"] == 2
    assert payload["prescription_count"] == 2
    assert payload["severity_counts"]["high"] == 1
    assert payload["severity_counts"]["medium"] == 1
    assert payload["judgment_next_move"] == "Fix release blockers."

    by_id = {item["diagnosis_id"]: item for item in payload["diagnoses"]}

    assert by_id["doctor.clean_tree"]["category"] == "release"
    assert by_id["doctor.clean_tree"]["status"] == "error"
    assert by_id["doctor.clean_tree"]["verification_commands"] == [
        "python -m sdetkit doctor --clean-tree --format json",
        "python -m sdetkit gate fast",
    ]

    assert by_id["doctor.deps"]["category"] == "dependency"
    assert by_id["doctor.deps"]["status"] == "warning"
    assert by_id["doctor.deps"]["evidence"] == ["requirements-test.txt missing httpx"]

    assert payload["prescriptions"][0]["priority"] == 85
    assert payload["next_commands"] == [
        "python -m sdetkit doctor --clean-tree --format json",
        "python -m sdetkit doctor --deps --format json",
    ]


def test_quality_failed_check_ids_without_check_entries_become_diagnoses():
    source = _clean_payload()
    source["quality"] = {"failed_check_ids": ["venv", "dev_tools"]}

    payload = doctor_diagnosis.build_diagnosis_payload(source)

    assert payload["diagnosis_count"] == 2
    assert [item["diagnosis_id"] for item in payload["diagnoses"]] == [
        "doctor.dev_tools",
        "doctor.venv",
    ]
    assert payload["diagnoses"][0]["source"] == "doctor.quality"


def test_cli_writes_json_output(tmp_path, capsys):
    source_path = tmp_path / "doctor.json"
    out_path = tmp_path / "diagnosis.json"
    source_path.write_text(json.dumps(_failed_payload()), encoding="utf-8")

    rc = doctor_diagnosis.main(
        ["--source", str(source_path), "--out", str(out_path), "--format", "json"]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["diagnosis_count"] == 2
    assert payload["severity"] == "high"


def test_cli_prints_text_output(tmp_path, capsys):
    source_path = tmp_path / "doctor.json"
    source_path.write_text(json.dumps(_failed_payload()), encoding="utf-8")

    rc = doctor_diagnosis.main(["--source", str(source_path), "--format", "text"])

    assert rc == 0

    output = capsys.readouterr().out
    assert "schema_version=sdetkit.doctor.diagnosis.v1" in output
    assert "diagnosis_count=2" in output
    assert "diagnosis=doctor.clean_tree" in output


def test_cli_rejects_invalid_json(tmp_path, capsys):
    source_path = tmp_path / "invalid.json"
    source_path.write_text("{not json", encoding="utf-8")

    rc = doctor_diagnosis.main(["--source", str(source_path)])

    assert rc == 2
    assert "error=" in capsys.readouterr().err
