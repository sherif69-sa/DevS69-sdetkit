import json

from sdetkit import adaptive_diagnosis


def _codes(payload):
    return [item["code"] for item in payload["diagnoses"]]


def _doctor_record(
    decision="SHIP", failed_step_count=0, diagnosis_count=0, prescription_count=0
):
    return {
        "decision": decision,
        "failed_step_count": failed_step_count,
        "doctor_cortex": {
            "enabled": True,
            "diagnosis": {"diagnosis_count": diagnosis_count},
            "prescriptions": {"prescription_count": prescription_count},
        },
    }


def test_clear_payload_when_evidence_has_no_signals():
    payload = adaptive_diagnosis.analyze_evidence(
        mission_control={
            "decision": "SHIP",
            "findings": ["ok"],
            "artifacts": ["report.json"],
        },
        ledger_records=[{"decision": "SHIP", "failed_step_count": 0}],
    )

    assert payload["schema_version"] == "sdetkit.adaptive.diagnosis.v1"
    assert payload["ok"] is True
    assert payload["status"] == "clear"
    assert payload["risk_score"] == 0
    assert payload["diagnosis_count"] == 0
    assert payload["diagnoses"] == []


def test_format_drift_comment_is_specific_and_safe():
    log_text = """
    pytest rc=0 passed
    ruff format..............................................................Failed
    - files were modified by this hook
    1 file reformatted
    /home/runner/work/secret-project/tests/test_new_feature.py
    secret-token-123
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnosis = payload["diagnoses"][0]
    rendered = json.dumps(payload, sort_keys=True)

    assert diagnosis["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert diagnosis["confidence"] == "high"
    assert diagnosis["affected_files"]
    assert diagnosis["affected_files"][0] == "tests/test_new_feature.py" or (
        "<redacted>" in diagnosis["affected_files"][0]
        and "<path>" in diagnosis["affected_files"][0]
    )
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is True
    assert "ruff format --check" in " ".join(diagnosis["proof_commands"])
    assert "pytest evidence appears green" in diagnosis["evidence"]
    assert "/home/runner" not in rendered
    assert "secret-project" not in rendered
    assert "secret-token" not in rendered


def test_pytest_assertion_failure_uses_first_test_as_fix_anchor():
    log_text = """
    FAILED tests/test_widget.py::test_widget_contract - AssertionError
    tests/test_widget.py::test_widget_contract
    """

    payload = adaptive_diagnosis.analyze_evidence(
        log_text=log_text,
        ledger_records=[{"decision": "SHIP", "failed_step_count": 0}],
    )
    diagnosis = payload["diagnoses"][0]

    assert payload["status"] == "needs_fix"
    assert diagnosis["code"] == "PYTEST_ASSERTION_FAILURE"
    assert diagnosis["severity"] == "high"
    assert diagnosis["evidence"] == [
        "pytest failure",
        "first_failed_test=tests/test_widget.py::test_widget_contract",
    ]
    assert diagnosis["proof_commands"] == [
        "PYTHONPATH=src python -m pytest -q tests/test_widget.py::test_widget_contract"
    ]


def test_mission_control_no_ship_and_evidence_gap_are_reported_together():
    payload = adaptive_diagnosis.analyze_evidence(
        mission_control={
            "decision": "NO_SHIP",
            "failed_step_count": 1,
            "steps": [{"id": "ruff_format", "status": "failed", "rc": 1}],
        },
        ledger_records=[{"decision": "SHIP", "failed_step_count": 0}],
    )

    assert payload["status"] == "needs_fix"
    assert _codes(payload)[:2] == [
        "MISSION_CONTROL_NO_SHIP",
        "EVIDENCE_ARTIFACT_MISSING",
    ]
    assert "failed_steps=ruff_format" in payload["diagnoses"][0]["evidence"]


def test_history_finds_repeated_release_friction_and_doctor_regressions():
    payload = adaptive_diagnosis.analyze_evidence(
        ledger_records=[
            _doctor_record("NO_SHIP", 1, diagnosis_count=1, prescription_count=0),
            _doctor_record("NO_SHIP", 1, diagnosis_count=3, prescription_count=2),
        ]
    )
    codes = set(_codes(payload))

    assert payload["status"] == "needs_fix"
    assert "MISSION_CONTROL_REPEATED_FAILURE_PATTERN" in codes
    assert "DOCTOR_CORTEX_DIAGNOSIS_REGRESSION" in codes
    assert "DOCTOR_CORTEX_PRESCRIPTION_REGRESSION" in codes
    repeated = payload["diagnoses"][0]
    assert repeated["repeat_count"] == 2
    assert "no_ship_count=2" in repeated["evidence"]


def test_adaptive_memory_empty_and_reusable_context_change_comment():
    empty = adaptive_diagnosis.analyze_evidence(
        ledger_records=[{"decision": "SHIP"}], adaptive_history={"run_count": 0}
    )
    learned = adaptive_diagnosis.analyze_evidence(
        ledger_records=[{"decision": "SHIP"}], adaptive_history={"run_count": 4}
    )

    assert _codes(empty) == ["LEARNING_DB_EMPTY"]
    assert _codes(learned) == ["KNOWN_ADAPTIVE_PATTERN_AVAILABLE"]
    assert empty["diagnoses"][0]["diagnosis"] != learned["diagnoses"][0]["diagnosis"]
    assert learned["diagnoses"][0]["repeat_count"] == 4


def test_text_and_markdown_render_operator_safe_content():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="FAILED tests/test_case.py::test_case - AssertionError at /tmp/secret-path.py secret-token",
        ledger_records=[{"decision": "SHIP"}],
    )

    text = adaptive_diagnosis.render_text(payload)
    markdown = adaptive_diagnosis.render_markdown(payload)

    assert "schema_version=sdetkit.adaptive.diagnosis.v1" in text
    assert "# Adaptive Diagnosis Intelligence" in markdown
    assert "Why developers miss it" in markdown
    assert "/tmp/" not in text + markdown
    assert "secret-token" not in text + markdown


def test_cli_writes_json_and_rejects_bad_jsonl(tmp_path, capsys):
    log_path = tmp_path / "quality.log"
    ledger_path = tmp_path / "mission-control.jsonl"
    output_path = tmp_path / "diagnosis.json"
    log_path.write_text("1 file reformatted\npytest rc=0\n", encoding="utf-8")
    ledger_path.write_text(json.dumps({"decision": "SHIP"}) + "\n", encoding="utf-8")

    rc = adaptive_diagnosis.main(
        [
            "--log",
            str(log_path),
            "--ledger",
            str(ledger_path),
            "--format",
            "json",
            "--out",
            str(output_path),
        ]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["diagnoses"][0]["code"] == "PRE_COMMIT_FORMAT_DRIFT"

    ledger_path.write_text("not-json\n", encoding="utf-8")
    rc = adaptive_diagnosis.main(["--ledger", str(ledger_path)])

    assert rc == 2
    assert "invalid JSONL at line 1" in capsys.readouterr().err
