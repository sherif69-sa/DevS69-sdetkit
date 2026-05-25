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
    assert any(
        item.startswith("candidate_scenarios=") and "CI_STEP_EXIT_NONZERO" in item
        for item in diagnosis["evidence"]
    )
    assert any(
        item.startswith("candidate_odds=") and "CI_STEP_EXIT_NONZERO:medium" in item
        for item in diagnosis["evidence"]
    )
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
        "package-manager-error": "npm ERR! lifecycle script failed",
    }

    for expected_signal, log_text in cases.items():
        payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)

        assert payload["diagnoses"][0]["code"] == "UNKNOWN_REVIEW_REQUIRED"
        assert f"matched_failure_signals={expected_signal}" in payload["diagnoses"][0]["evidence"]
        assert payload["fix_plan"][0]["safe_to_auto_fix"] is False


def test_coverage_failure_signal_routes_to_specific_coverage_gate_regression():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="coverage fail under configured threshold"
    )

    codes = {diagnosis["code"] for diagnosis in payload["diagnoses"]}
    assert "COVERAGE_GATE_REGRESSION" in codes
    assert "UNKNOWN_REVIEW_REQUIRED" not in codes
    assert "matched_failure_signals=coverage-failure" in payload["diagnoses"][0]["evidence"][0]


def test_seeded_scenario_database_recommends_package_install_checks():
    payload = adaptive_diagnosis.analyze_evidence(log_text="npm ERR! lifecycle script failed")
    diagnosis = payload["diagnoses"][0]

    assert any(
        item.startswith("candidate_scenarios=") and "PACKAGE_INSTALL_FAILURE" in item
        for item in diagnosis["evidence"]
    )
    assert any(
        item.startswith("candidate_odds=") and "PACKAGE_INSTALL_FAILURE:medium" in item
        for item in diagnosis["evidence"]
    )
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
    assert diagnosis["evidence"][:2] == [
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
    assert int(seeded_count.split("=", 1)[1]) >= 25
    odds_size = next(
        item
        for item in empty["diagnoses"][0]["evidence"]
        if item.startswith("seeded_odds_space_size=")
    )
    assert int(odds_size.split("=", 1)[1]) >= 1_000_000_000
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


def _scenario_pack_payload(**overrides):
    payload = {
        "schema_version": "sdetkit.adaptive.scenario_pack.v1",
        "pack_id": "test.pack",
        "title": "Test pack",
        "scenarios": [
            {
                "code": "TEST_SIGNAL",
                "title": "Test signal",
                "signals": ["error-prefix"],
                "keywords": ["test signal"],
                "checks": ["Check the test signal."],
                "commands": ["python -m pytest -q tests/test_signal.py"],
                "risk_band": "medium",
                "prior_weight": 2,
                "tags": ["test"],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_builtin_scenario_pack_is_schema_validated_data_product():
    scenarios = adaptive_diagnosis.SEEDED_SCENARIO_DB
    codes = [scenario.code for scenario in scenarios]

    assert len(scenarios) >= 5000
    assert len(adaptive_diagnosis.GENERATED_SCENARIO_DB) >= 5000
    assert codes == sorted(codes)
    assert "PACKAGE_INSTALL_FAILURE" in codes
    assert all(scenario.checks and scenario.commands for scenario in scenarios)


def test_scenario_pack_loader_rejects_malformed_pack(tmp_path):
    pack_path = tmp_path / "bad-scenarios.json"
    payload = _scenario_pack_payload()
    del payload["scenarios"][0]["commands"]
    pack_path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        adaptive_diagnosis.load_scenario_pack(pack_path)
    except ValueError as exc:
        assert "missing required fields: commands" in str(exc)
    else:
        raise AssertionError("expected malformed scenario pack to be rejected")


def test_layered_scenario_packs_merge_deterministically(tmp_path):
    local_dir = tmp_path / ".sdetkit" / "adaptive"
    local_dir.mkdir(parents=True)
    local_pack = local_dir / "scenarios.json"
    local_pack.write_text(json.dumps(_scenario_pack_payload()), encoding="utf-8")

    scenarios = adaptive_diagnosis.load_layered_scenarios(tmp_path)
    codes = [scenario.code for scenario in scenarios]

    assert codes == sorted(codes)
    assert "TEST_SIGNAL" in codes
    assert len(codes) == len(set(codes))


def test_learning_calibration_reranks_unknown_candidate_scenarios():
    adaptive_history = {
        "schema_version": "sdetkit.adaptive.learn.summary.v1",
        "top_recurring_scenarios": [
            {
                "code": "RELEASE_VERSION_CONFLICT",
                "calibration": {
                    "primary_action": "promote_and_increase_risk",
                    "actions": ["promote", "increase_risk"],
                    "confidence_delta": 2,
                    "risk_delta": 12,
                },
            },
            {
                "code": "CACHE_ARTIFACT_POISONING",
                "calibration": {
                    "primary_action": "demote",
                    "actions": ["demote"],
                    "confidence_delta": -2,
                    "risk_delta": -8,
                },
            },
        ],
    }

    payload = adaptive_diagnosis.analyze_evidence(
        log_text="Error: command failed",
        adaptive_history=adaptive_history,
    )
    diagnosis = payload["diagnoses"][0]

    assert diagnosis["code"] == "UNKNOWN_REVIEW_REQUIRED"
    assert any(
        item.startswith("candidate_scenarios=RELEASE_VERSION_CONFLICT")
        for item in diagnosis["evidence"]
    )
    assert any(
        item.startswith("candidate_calibration=RELEASE_VERSION_CONFLICT:promote_and_increase_risk")
        for item in diagnosis["evidence"]
    )
    assert diagnosis["recommended_fix"][0].startswith("Check candidate RELEASE_VERSION_CONFLICT")
    assert diagnosis["proof_commands"][:2] == [
        "git tag --points-at HEAD",
        "python -m build --sdist --wheel",
    ]


def test_layered_scenario_pack_report_emits_source_metadata(tmp_path):
    local_dir = tmp_path / ".sdetkit" / "adaptive"
    local_dir.mkdir(parents=True)
    local_pack = local_dir / "scenarios.json"
    local_pack.write_text(json.dumps(_scenario_pack_payload()), encoding="utf-8")

    report = adaptive_diagnosis.layered_scenario_pack_report(tmp_path)

    assert report["schema_version"] == "sdetkit.adaptive.scenario_pack_report.v1"
    assert report["layer_count"] == 2
    assert [layer["source"] for layer in report["layers"]] == ["builtin", "repo-local"]
    assert "TEST_SIGNAL" in report["merged_codes"]
    assert report["overrides"] == []


def test_layered_scenario_pack_report_rejects_unapproved_overrides(tmp_path):
    local_dir = tmp_path / ".sdetkit" / "adaptive"
    local_dir.mkdir(parents=True)
    local_pack = local_dir / "scenarios.json"
    payload = _scenario_pack_payload()
    payload["scenarios"][0]["code"] = "PACKAGE_INSTALL_FAILURE"
    local_pack.write_text(json.dumps(payload), encoding="utf-8")

    try:
        adaptive_diagnosis.validate_layered_scenario_packs(tmp_path)
    except ValueError as exc:
        assert "PACKAGE_INSTALL_FAILURE" in str(exc)
        assert "override-approved" in str(exc)
    else:
        raise AssertionError("expected unapproved scenario override to be rejected")


def test_layered_scenario_pack_report_allows_approved_overrides(tmp_path):
    local_dir = tmp_path / ".sdetkit" / "adaptive"
    local_dir.mkdir(parents=True)
    local_pack = local_dir / "scenarios.json"
    payload = _scenario_pack_payload()
    payload["scenarios"][0]["code"] = "PACKAGE_INSTALL_FAILURE"
    payload["scenarios"][0]["title"] = "Approved package install override"
    payload["scenarios"][0]["tags"] = ["test", "override-approved"]
    local_pack.write_text(json.dumps(payload), encoding="utf-8")

    report = adaptive_diagnosis.validate_layered_scenario_packs(tmp_path)
    scenarios = adaptive_diagnosis.load_layered_scenarios(tmp_path)
    overridden = {scenario.code: scenario for scenario in scenarios}["PACKAGE_INSTALL_FAILURE"]

    assert report["overrides"] == [
        {
            "code": "PACKAGE_INSTALL_FAILURE",
            "previous_source": "builtin",
            "source": "repo-local",
            "approved": True,
            "approval_tag": "override-approved",
        }
    ]
    assert overridden.title == "Approved package install override"


def test_adaptive_diagnosis_operator_guidance_uses_observed_failure_lines() -> None:
    log_text = """
    FAILED tests/test_real_checkout.py::test_checkout_total - AssertionError
    E   AssertionError: expected 42 but got 41
    Process completed with exit code 1
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    diagnosis = payload["diagnoses"][0]
    guidance = diagnosis["operator_guidance"]

    assert diagnosis["code"] == "PYTEST_ASSERTION_FAILURE"
    assert guidance["matched_from_current_log"] is True
    assert guidance["automation_boundary"] == "review_first_no_auto_mutation"
    assert guidance["what_to_fix_first"] == "Reproduce the first failing test only."
    assert any(
        "test_real_checkout.py::test_checkout_total" in line
        for line in guidance["observed_failure_lines"]
    )
    assert any(item.startswith("observed_failure_line_1=") for item in diagnosis["evidence"])
    assert "random" in guidance["why_this_is_not_random"]


def test_adaptive_diagnosis_safe_mechanical_guidance_boundary() -> None:
    log_text = """
    ruff check..............................................................Failed
    tests/test_api.py:2:21: F401 [*] `pathlib.Path` imported but unused
    Found 1 error.
    [*] 1 fixable with the `--fix` option.
    """

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    guidance = payload["diagnoses"][0]["operator_guidance"]

    assert payload["diagnoses"][0]["code"] == "RUFF_FIXABLE_LINT"
    assert guidance["automation_boundary"] == "safe_mechanical_fix_allowed_after_proof"
    assert guidance["affected_files"] == ["tests/test_api.py"]
    assert "ruff check --fix" in " ".join(guidance["how_to_fix"])


def test_adaptive_scenario_database_scales_to_real_world_matrix() -> None:
    payload = adaptive_diagnosis.analyze_evidence(
        log_text=(
            "FAILED tests/test_api.py::test_contract - AssertionError\n"
            "mypy src/app.py:10: error: Argument 1 has incompatible type [arg-type]\n"
            "ruff check Failed Found 1 error.\n"
            "npm ERR! lifecycle script failed\n"
            "coverage fail under configured threshold\n"
            "Process completed with exit code 1"
        )
    )

    db = payload["scenario_database"]
    assert db["curated_scenario_count"] >= 25
    assert db["generated_matrix_scenario_count"] >= 5000
    assert db["total_scenario_count"] >= 5000
    codes = {diagnosis["code"] for diagnosis in payload["diagnoses"]}
    assert "PYTEST_ASSERTION_FAILURE" in codes
    assert "MYPY_TYPE_CONTRACT_DRIFT" in codes
    assert any(
        "observed_failure_line_" in evidence
        for diagnosis in payload["diagnoses"]
        for evidence in diagnosis["evidence"]
    )


def test_generated_matrix_candidates_are_not_fixed_three_scenarios() -> None:
    candidates = adaptive_diagnosis._candidate_scenarios(
        "github actions pytest timeout flaky_rerun Process completed with exit code 1",
        limit=80,
    )

    assert len(adaptive_diagnosis.SEEDED_SCENARIO_DB) >= 5000
    assert any(candidate.code.startswith("MATRIX_") for candidate in candidates)
    assert len({candidate.code for candidate in candidates}) > 3


def test_dependency_resolver_failure_is_specific_not_unknown():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="\n".join(
            [
                "ERROR: Cannot install -r requirements-test.txt because these package versions have conflicting dependencies.",
                "ResolutionImpossible: for help visit https://pip.pypa.io/",
                "Process completed with exit code 1",
            ]
        )
    )

    assert "PACKAGE_INSTALL_FAILURE" in _codes(payload)
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == "PACKAGE_INSTALL_FAILURE"
    assert "pip install -c constraints-ci.txt -r requirements-test.txt -e ." in " ".join(
        diagnosis["proof_commands"]
    )
    assert payload["fix_plan"][0]["safe_to_auto_fix"] is False


def test_security_gate_failure_is_specific_not_quality_noise():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="\n".join(
            [
                "sdetkit-security-gate / High entropy string",
                "High-entropy string literal detected.",
                "Process completed with exit code 1",
            ]
        )
    )

    assert "SECURITY_FINDING_REVIEW_REQUIRED" in _codes(payload)
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == "SECURITY_FINDING_REVIEW_REQUIRED"
    assert "pre_commit run -a" in " ".join(diagnosis["proof_commands"])


def test_release_artifact_failure_is_specific_not_coverage_noise():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="\n".join(
            [
                "Run python -m build && python -m twine check dist/*",
                "ERROR InvalidDistribution: Metadata is missing required fields",
                "Process completed with exit code 1",
                "Total coverage: 96.69%",
            ]
        )
    )

    assert "RELEASE_ARTIFACT_INVALID" in _codes(payload)
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == "RELEASE_ARTIFACT_INVALID"
    assert "twine check dist/*" in " ".join(diagnosis["proof_commands"])


def test_workflow_contract_failure_is_specific():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="\n".join(
            [
                "Invalid workflow file: .github/workflows/pr-quality-comment.yml#L42",
                "The workflow is not valid. .github/workflows/pr-quality-comment.yml (Line: 42, Col: 9): Unexpected value",
                "Process completed with exit code 1",
            ]
        )
    )

    assert "WORKFLOW_CONTRACT_FAILURE" in _codes(payload)
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == "WORKFLOW_CONTRACT_FAILURE"
    assert "test_pr_quality_adaptive_sentinel_workflow.py" in " ".join(diagnosis["proof_commands"])


def test_docs_build_failure_is_specific():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="\n".join(
            [
                "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict",
                "mkdocs.exceptions.ConfigurationError: Documentation file 'missing.md' not found in docs_dir",
                "Process completed with exit code 1",
            ]
        )
    )

    assert "DOCS_BUILD_CONTRACT" in _codes(payload)
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == "DOCS_BUILD_CONTRACT"
    assert "mkdocs build --strict" in " ".join(diagnosis["proof_commands"])


def test_cli_contract_failure_is_specific():
    payload = adaptive_diagnosis.analyze_evidence(
        log_text="\n".join(
            [
                "usage: sdetkit [-h] {investigate,adaptive,doctor} ...",
                "sdetkit: error: unrecognized arguments: --broken-flag",
                "Process completed with exit code 2",
            ]
        )
    )

    assert "CLI_CONTRACT_FAILURE" in _codes(payload)
    assert "UNKNOWN_REVIEW_REQUIRED" not in _codes(payload)
    diagnosis = payload["diagnoses"][0]
    assert diagnosis["code"] == "CLI_CONTRACT_FAILURE"
    assert "python -m sdetkit --help" in " ".join(diagnosis["proof_commands"])


def test_ruff_b011_assertionerror_advice_does_not_create_pytest_failure() -> None:
    lint_rule = "".join(("B", "011"))
    assertion_name = "".join(("Assertion", "Error"))
    finding_path = "/".join(("tests", "test_controlled_actions_log_acquisition_probe.py"))
    advice = (
        f"{lint_rule} Do not `assert False` (`python -O` removes these calls), "
        f"raise `{assertion_name}()`"
    )
    log_text = "\n".join(
        [
            "Run python -m ruff check src tests",
            advice,
            f" --> {finding_path}:2:12",
            "Found 1 error.",
            "No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).",
            "Process completed with exit code 1.",
        ]
    )

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    codes = _codes(payload)

    assert "RUFF_LINT_FAILURE" in codes
    assert "PYTEST_ASSERTION_FAILURE" not in codes
    ruff = next(item for item in payload["diagnoses"] if item["code"] == "RUFF_LINT_FAILURE")
    assert ruff["operator_guidance"]["automation_boundary"] == "review_first_no_auto_mutation"


def test_timestamp_prefixed_ruff_b011_advice_stays_ruff_not_pytest() -> None:
    lint_rule = "".join(("B", "011"))
    assertion_name = "".join(("Assertion", "Error"))
    finding_path = "/".join(("tests", "test_controlled_actions_log_acquisition_probe.py"))
    job_prefix = "Fast CI lane (py3.11) Ruff lint baseline "
    timestamp = "".join(("2026-05", "-24T23", ":45:53", ".8020241Z"))
    advice = (
        f"{lint_rule} Do not `assert False` (`python -O` removes these calls), "
        f"raise `{assertion_name}()`"
    )
    log_text = "\n".join(
        [
            f"{job_prefix}{timestamp} Run python -m ruff check src tests",
            f"{job_prefix}{timestamp} {advice}",
            f"{job_prefix}{timestamp}  --> {finding_path}:2:12",
            f"{job_prefix}{timestamp} Found 1 error.",
            f"{job_prefix}{timestamp} No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).",
            f"Fast CI lane (py3.11) Complete job {timestamp} Process completed with exit code 1.",
        ]
    )

    payload = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    codes = _codes(payload)

    assert "RUFF_LINT_FAILURE" in codes
    assert "PYTEST_ASSERTION_FAILURE" not in codes
    ruff = next(item for item in payload["diagnoses"] if item["code"] == "RUFF_LINT_FAILURE")
    assert ruff["operator_guidance"]["automation_boundary"] == "review_first_no_auto_mutation"
