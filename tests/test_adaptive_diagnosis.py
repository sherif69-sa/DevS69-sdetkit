import json

from sdetkit import adaptive_diagnosis


def _codes(payload):
    return [item["code"] for item in payload["diagnoses"]]


def _doctor_record(decision="SHIP", failed_step_count=0, diagnosis_count=0, prescription_count=0):
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


def test_green_quality_log_does_not_create_unknown_review_required():
    log_text = """
    ✅ quality.sh cov passed
    ruff check..............................................................Passed
    ruff format --check.....................................................Passed
    mypy....................................................................Passed
    tests/test_widget.py::test_widget_contract PASSED
    128 passed in 12.34s
    Total coverage: 96.25%
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)

    assert payload["status"] == "clear"
    assert payload["ok"] is True
    assert payload["diagnosis_count"] == 0
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)


def test_unknown_failure_like_log_stays_review_first():
    log_text = """
    custom quality gate emitted an unrecognized integrity report
    Process completed with exit code 42
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)

    assert payload["status"] in {"needs_attention", "needs_fix"}
    assert payload["diagnoses"][0]["code"] == "UNKNOWN_REVIEW_REQUIRED"
    diagnosis = payload["diagnoses"][0]
    assert "matched_failure_signals=ci-exit-code" in diagnosis["evidence"]
    assert "The CI step ended with a non-zero process exit code." in diagnosis["evidence"]
    assert "candidate_scenarios=CI_STEP_EXIT_NONZERO" in diagnosis["evidence"]
    assert any(
        "Check candidate CI_STEP_EXIT_NONZERO" in fix for fix in diagnosis["recommended_fix"]
    )
    assert "python -m pre_commit run -a" in diagnosis["proof_commands"]
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is False


def test_failure_signal_database_ignores_success_counters():
    log_text = """
    mypy....................................................................Passed
    ruff check..............................................................Passed
    Found 0 errors.
    pytest summary: 0 failed, 128 passed, 0 errors
    Process completed with exit code 0
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)

    assert payload["status"] == "clear"
    assert payload["diagnosis_count"] == 0


def test_failure_signal_database_covers_unclassified_failure_families():
    cases = {
        "error-prefix": "build tool Error: unexpected integrity result",
        "gate-problems-found": "quality gate: problems found in custom policy",
        "failed-steps": "summary failed_steps=custom_policy",
        "coverage-failure": "coverage fail under configured threshold",
        "package-manager-error": "npm ERR! lifecycle script failed",
    }

    for expected_signal, log_text in cases.items():
        payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)

        assert payload["diagnoses"][0]["code"] == "UNKNOWN_REVIEW_REQUIRED"
        assert f"matched_failure_signals={expected_signal}" in payload["diagnoses"][0]["evidence"]
        assert payload["fix_plan"][0]["safe_to_auto_fix"] is False


def test_seeded_scenario_database_recommends_package_install_checks():
    payload = adaptive_diagnosis.analyze_evidence(log_text="npm ERR! lifecycle script failed")
    diagnosis = payload["diagnoses"][0]

    assert "candidate_scenarios=PACKAGE_INSTALL_FAILURE" in diagnosis["evidence"]
    assert any(
        "Check candidate PACKAGE_INSTALL_FAILURE" in fix for fix in diagnosis["recommended_fix"]
    )
    assert "python -m pip install -r requirements-test.txt -e ." in diagnosis["proof_commands"]


def test_format_drift_comment_is_specific_and_safe():
    log_text = """
    pytest rc=0 passed
    ruff format..............................................................Failed
    - files were modified by this hook
    1 file reformatted
    /home/runner/work/secret-project/tests/test_new_feature.py
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


def test_ruff_fixable_lint_comment_is_specific_and_safe():
    log_text = """
    ruff check..............................................................Failed
    tests/test_maintenance_autopilot_safe_remediation.py:2:21: F401 [*] `pathlib.Path` imported but unused
    help: Remove unused import: `pathlib.Path`
    Found 1 error.
    [*] 1 fixable with the `--fix` option.
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnosis = payload["diagnoses"][0]

    assert payload["status"] == "needs_fix"
    assert diagnosis["code"] == "RUFF_FIXABLE_LINT"
    assert diagnosis["confidence"] == "high"
    assert diagnosis["affected_files"] == ["tests/test_maintenance_autopilot_safe_remediation.py"]
    assert "ruff_rules=F401" in diagnosis["evidence"]
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is True
    assert "ruff check --fix" in " ".join(diagnosis["recommended_fix"])


def test_ruff_import_sorting_is_specific_and_safe():
    log_text = """
    ruff check..............................................................Failed
    src/sdetkit/adaptive_safe_fix.py:1:1: I001 [*] Import block is un-sorted or un-formatted
    Found 1 error.
    [*] 1 fixable with the `--fix` option.
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnosis = payload["diagnoses"][0]

    assert diagnosis["code"] == "RUFF_FIXABLE_LINT"
    assert diagnosis["affected_files"] == ["src/sdetkit/adaptive_safe_fix.py"]
    assert "ruff_rules=I001" in diagnosis["evidence"]
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is True


def test_ruff_fixable_lint_keeps_logic_risk_rules_review_required():
    log_text = """
    ruff check..............................................................Failed
    src/sdetkit/example.py:10:5: B006 [*] Do not use mutable data structures for argument defaults
    Found 1 error.
    [*] 1 fixable with the `--fix` option.
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnosis = payload["diagnoses"][0]

    assert diagnosis["code"] == "RUFF_LINT_FAILURE"
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is False


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
    seeded_count = next(
        item
        for item in empty["diagnoses"][0]["evidence"]
        if item.startswith("seeded_scenario_count=")
    )
    assert int(seeded_count.split("=", 1)[1]) >= 10
    assert any(
        "seeded scenario database" in fix for fix in empty["diagnoses"][0]["recommended_fix"]
    )
    assert learned["diagnoses"][0]["repeat_count"] == 4


def test_text_and_markdown_render_operator_safe_content():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="FAILED tests/test_case.py::test_case - AssertionError at /tmp/secret-path.py",
        ledger_records=[{"decision": "SHIP"}],
    )

    text = adaptive_diagnosis.render_text(payload)
    markdown = adaptive_diagnosis.render_markdown(payload)

    assert "schema_version=sdetkit.adaptive.diagnosis.v1" in text
    assert "# Adaptive Diagnosis Intelligence" in markdown
    assert "Why developers miss it" in markdown
    assert "/tmp/" not in text + markdown
    assert "secret-path" not in text + markdown


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


def test_local_investigation_failure_classes_are_review_first():
    cases = [
        (
            "MISSING_TEST_DEPENDENCY",
            "Exit: Missing test dependencies: hypothesis, yaml. Install test requirements.",
        ),
        (
            "PYTHON_RUNTIME_COMPATIBILITY",
            "ImportError: cannot import name 'UTC' from 'datetime'",
        ),
        (
            "LOCAL_ENVIRONMENT_FRICTION",
            "pip stuck in /mnt/c/Users/Pika/repo/.venv/lib/python3.11/site-packages KeyboardInterrupt",
        ),
        (
            "BROKEN_TEST_DOUBLE",
            "TypeError: Resp() takes no arguments because test double defines init_ instead of __init__",
        ),
        (
            "MISSING_PUBLIC_API_PARITY",
            "AttributeError: SdetAsyncHttpClient object has no attribute get_json_list_paginated_envelope async parity",
        ),
        (
            "GIT_BRANCH_DIVERGED",
            "Updates were rejected because the remote contains work that you do not have locally. fetch first non-fast-forward",
        ),
        (
            "REMOTE_BRANCH_DRIFT",
            "Successfully rebased and updated refs/heads/feature/test from origin/feature/test",
        ),
        (
            "PRODUCT_LOGIC_FAILURE",
            "Product logic failure: deterministic product behavior failure in widget contract",
        ),
        (
            "UNKNOWN_REVIEW_REQUIRED",
            "command failed with unusual tool output that does not match known patterns",
        ),
    ]

    for expected, log_text in cases:
        payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
        diagnosis = payload["diagnoses"][0]
        assert diagnosis["code"] == expected
        assert payload["fix_plan"][0]["safe_to_auto_fix"] is False


def test_safe_auto_fix_codes_remain_narrow_for_local_investigation_classes():
    unsafe_logs = [
        "Exit: Missing test dependencies: hypothesis, yaml.",
        "ImportError: cannot import name 'UTC' from 'datetime'",
        "TypeError: Resp() takes no arguments because test double defines init_ instead of __init__",
        "AttributeError: SdetAsyncHttpClient object has no attribute get_json_list_paginated_envelope async parity",
        "Product logic failure: deterministic product behavior failure in widget contract",
    ]

    for log_text in unsafe_logs:
        payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
        assert payload["fix_plan"][0]["safe_to_auto_fix"] is False

    safe_payload = adaptive_diagnosis.analyze_evidence(
        log_text="ruff format failed\n1 file reformatted\n"
    )
    assert safe_payload["diagnoses"][0]["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert safe_payload["fix_plan"][0]["safe_to_auto_fix"] is True
