import json

from sdetkit import adaptive_safe_fix


def _payload(code="PRE_COMMIT_FORMAT_DRIFT", status="needs_fix", severity="medium", confidence="high"):
    return {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "ok": False,
        "status": status,
        "risk_score": 53,
        "confidence": confidence,
        "summary": "Primary issue.",
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": code,
                "severity": severity,
                "confidence": confidence,
                "title": "Formatter drift blocked pre-commit",
                "recommended_fix": ["Run ruff format on touched files."],
                "proof_commands": ["PYTHONPATH=src python -m pytest -q tests/test_case.py"],
                "risk_if_ignored": "CI stays red.",
                "learning_signal": "formatting-drift-after-green-tests",
                "repeat_count": 1,
                "affected_files": ["src/sdetkit/example.py", "tests/test_example.py"],
            }
        ],
        "fix_plan": [],
        "learning_updates": [],
    }


def test_formatter_drift_builds_safe_format_only_plan():
    plan = adaptive_safe_fix.build_plan(_payload())

    assert plan["schema_version"] == "sdetkit.adaptive_safe_fix.v1"
    assert plan["safe_to_auto_fix"] is True
    assert plan["fix_type"] == "format_only"
    assert plan["requires_human_review"] is False
    assert plan["confidence"] == "high"
    assert plan["affected_files"] == ["src/sdetkit/example.py", "tests/test_example.py"]
    assert plan["commands"] == [
        "PYTHONPATH=src python -m ruff format src/sdetkit/example.py tests/test_example.py",
        "PYTHONPATH=src python -m ruff format --check src/sdetkit/example.py tests/test_example.py",
        "PYTHONPATH=src python -m ruff check src/sdetkit/example.py tests/test_example.py",
    ]
    assert plan["proof_commands"][0].endswith(
        "ruff format --check src/sdetkit/example.py tests/test_example.py"
    )
    assert "pytest" in plan["proof_commands"][1]


def test_formatter_drift_without_files_uses_placeholder_targets():
    payload = _payload()
    payload["diagnoses"][0]["affected_files"] = []

    plan = adaptive_safe_fix.build_plan(payload)

    assert plan["safe_to_auto_fix"] is True
    assert plan["commands"][0].endswith("ruff format <touched-python-files>")


def test_non_formatter_diagnoses_require_human_review():
    for code in [
        "PYTEST_ASSERTION_FAILURE",
        "PYTEST_IMPORT_FAILURE",
        "MYPY_TYPE_CONTRACT_DRIFT",
        "MISSION_CONTROL_NO_SHIP",
        "DOCTOR_CORTEX_DIAGNOSIS_REGRESSION",
        "RUFF_LINT_FAILURE",
    ]:
        plan = adaptive_safe_fix.build_plan(_payload(code=code))
        assert plan["safe_to_auto_fix"] is False
        assert plan["requires_human_review"] is True
        assert plan["fix_type"] == "review_required"
        assert code in plan["reason"]


def test_formatter_drift_requires_actionable_high_confidence_low_or_medium_severity():
    assert adaptive_safe_fix.build_plan(_payload(status="monitor"))["safe_to_auto_fix"] is False
    assert adaptive_safe_fix.build_plan(_payload(confidence="medium"))["safe_to_auto_fix"] is False
    assert adaptive_safe_fix.build_plan(_payload(severity="high"))["safe_to_auto_fix"] is False


def test_empty_diagnosis_requires_review():
    payload = _payload()
    payload["diagnoses"] = []

    plan = adaptive_safe_fix.build_plan(payload)

    assert plan["safe_to_auto_fix"] is False
    assert plan["requires_human_review"] is True
    assert plan["source_code"] == "UNKNOWN"
    assert plan["commands"] == []


def test_plan_from_file_writes_output(tmp_path):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    plan_path = tmp_path / "safe-fix-plan.json"
    diagnosis_path.write_text(json.dumps(_payload()), encoding="utf-8")

    plan = adaptive_safe_fix.plan_from_file(diagnosis_path, plan_path)

    assert plan["safe_to_auto_fix"] is True
    assert plan["source_path"] == diagnosis_path.as_posix()
    written = json.loads(plan_path.read_text(encoding="utf-8"))
    assert written["fix_type"] == "format_only"


def test_cli_outputs_json_and_rejects_bad_schema(tmp_path, capsys):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    plan_path = tmp_path / "safe-fix-plan.json"
    diagnosis_path.write_text(json.dumps(_payload()), encoding="utf-8")

    rc = adaptive_safe_fix.main(
        [str(diagnosis_path), "--out", str(plan_path), "--format", "json"]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["safe_to_auto_fix"] is True
    assert plan_path.exists()

    diagnosis_path.write_text(json.dumps({"schema_version": "bad"}), encoding="utf-8")
    rc = adaptive_safe_fix.main([str(diagnosis_path)])

    assert rc == 2
    assert "unsupported adaptive diagnosis schema" in capsys.readouterr().out
