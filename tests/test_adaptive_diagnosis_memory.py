import json

from sdetkit import adaptive_diagnosis_memory


def _diagnosis_payload(status="needs_fix"):
    return {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "ok": False,
        "status": status,
        "risk_score": 53,
        "confidence": "high",
        "summary": "Primary issue: Formatter drift blocked pre-commit.",
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": "PRE_COMMIT_FORMAT_DRIFT",
                "severity": "medium",
                "confidence": "high",
                "title": "Formatter drift blocked pre-commit",
                "diagnosis": "ruff-format changed files after tests passed.",
                "why_developers_miss_it": "Developers often see green tests first.",
                "evidence": [
                    "matched_failure_signals=ruff-format-failure,explicit-failed",
                    "candidate_scenarios=RUFF_FORMAT_DRIFT,PRE_COMMIT_HOOK_FAILURE",
                    "ruff-format modified files",
                ],
                "recommended_fix": ["Run ruff format on touched files."],
                "proof_commands": [
                    "PYTHONPATH=src python -m ruff format --check <touched-python-files>"
                ],
                "risk_if_ignored": "CI stays red.",
                "learning_signal": "formatting-drift-after-green-tests",
                "repeat_count": 2,
                "affected_files": ["tests/test_case.py"],
            }
        ],
        "fix_plan": [],
        "learning_updates": [],
    }


def test_build_safe_fix_learning_record_captures_remediation_and_commit_outcome():
    record = adaptive_diagnosis_memory.build_safe_fix_learning_record(
        plan={
            "schema_version": "sdetkit.adaptive_safe_fix.v1",
            "source_status": "needs_fix",
            "source_code": "RUFF_FIXABLE_LINT",
            "safe_to_auto_fix": True,
            "fix_type": "ruff_fixable_lint",
            "confidence": "high",
            "requires_human_review": False,
            "reason": "safe narrow lint",
            "commands": ["PYTHONPATH=src python -m ruff check --fix tests/test_case.py"],
            "proof_commands": ["PYTHONPATH=src python -m ruff check tests/test_case.py"],
            "affected_files": ["tests/test_case.py"],
        },
        remediation_result={
            "ok": True,
            "status": "success",
            "attempted": True,
            "command_count": 4,
        },
        commit_result={
            "ok": True,
            "attempted": True,
            "pushed": True,
            "reason": "safe mechanical fix committed and pushed",
        },
        learned_at_utc="2026-05-05T00:00:00Z",
    )

    assert record["source"] == "adaptive_safe_fix"
    assert record["code"] == "RUFF_FIXABLE_LINT"
    assert record["fix_type"] == "ruff_fixable_lint"
    assert record["affected_file_count"] == 1
    assert record["remediation_attempted"] is True
    assert record["remediation_ok"] is True
    assert record["remediation_status"] == "success"
    assert record["remediation_command_count"] == 4
    assert record["commit_attempted"] is True
    assert record["commit_ok"] is True
    assert record["commit_pushed"] is True
    assert record["learned_at_utc"] == "2026-05-05T00:00:00Z"
    assert len(record["record_id"]) == 16


def test_build_safe_fix_memory_rollup_groups_success_rates():
    format_record = adaptive_diagnosis_memory.build_safe_fix_learning_record(
        plan={
            "schema_version": "sdetkit.adaptive_safe_fix.v1",
            "source_status": "needs_fix",
            "source_code": "PRE_COMMIT_FORMAT_DRIFT",
            "safe_to_auto_fix": True,
            "fix_type": "format_only",
            "confidence": "high",
            "requires_human_review": False,
            "commands": ["PYTHONPATH=src python -m ruff format tests/test_case.py"],
            "proof_commands": ["PYTHONPATH=src python -m ruff format --check tests/test_case.py"],
            "affected_files": ["tests/test_case.py"],
        },
        remediation_result={"ok": True, "status": "success", "attempted": True, "command_count": 3},
        commit_result={"ok": False, "attempted": False, "pushed": False, "reason": "disabled"},
        learned_at_utc="2026-05-05T00:00:00Z",
    )
    ruff_record = adaptive_diagnosis_memory.build_safe_fix_learning_record(
        plan={
            "schema_version": "sdetkit.adaptive_safe_fix.v1",
            "source_status": "needs_fix",
            "source_code": "RUFF_FIXABLE_LINT",
            "safe_to_auto_fix": True,
            "fix_type": "ruff_fixable_lint",
            "confidence": "high",
            "requires_human_review": False,
            "commands": ["PYTHONPATH=src python -m ruff check --fix tests/test_case.py"],
            "proof_commands": ["PYTHONPATH=src python -m ruff check tests/test_case.py"],
            "affected_files": ["tests/test_case.py", "src/sdetkit/example.py"],
        },
        remediation_result={"ok": True, "status": "success", "attempted": True, "command_count": 4},
        commit_result={"ok": True, "attempted": True, "pushed": True, "reason": "pushed"},
        learned_at_utc="2026-05-05T00:01:00Z",
    )

    rollup = adaptive_diagnosis_memory.build_safe_fix_memory_rollup(
        [format_record, ruff_record, {"source": "adaptive_diagnosis"}]
    )

    assert rollup["schema_version"] == "sdetkit.adaptive_safe_fix.rollup.v1"
    assert rollup["safe_fix_records"] == 2
    assert rollup["group_count"] == 2
    by_type = {group["fix_type"]: group for group in rollup["groups"]}
    assert by_type["format_only"]["remediation_success_rate"] == 1.0
    assert by_type["format_only"]["commit_push_rate"] == 0.0
    assert by_type["ruff_fixable_lint"]["affected_file_count"] == 2
    assert by_type["ruff_fixable_lint"]["commit_push_rate"] == 1.0
    assert by_type["ruff_fixable_lint"]["latest_remediation_status"] == "success"


def test_safe_fix_rollup_from_db_reads_jsonl(tmp_path):
    db_path = tmp_path / "adaptive-safe-fix-memory.jsonl"
    record = adaptive_diagnosis_memory.build_safe_fix_learning_record(
        plan={
            "schema_version": "sdetkit.adaptive_safe_fix.v1",
            "source_code": "RUFF_FIXABLE_LINT",
            "safe_to_auto_fix": True,
            "fix_type": "ruff_fixable_lint",
            "requires_human_review": False,
            "affected_files": ["tests/test_case.py"],
        },
        remediation_result={"ok": False, "status": "failed", "attempted": True, "command_count": 2},
        commit_result={
            "ok": False,
            "attempted": False,
            "pushed": False,
            "reason": "remediation failed",
        },
        learned_at_utc="2026-05-05T00:00:00Z",
    )
    adaptive_diagnosis_memory.append_learning_records(db_path, [record])

    rollup = adaptive_diagnosis_memory.safe_fix_rollup_from_db(db_path)

    assert rollup["safe_fix_records"] == 1
    assert rollup["groups"][0]["remediation_success_rate"] == 0.0
    assert rollup["groups"][0]["latest_remediation_status"] == "failed"


def test_build_learning_records_from_actionable_diagnosis():
    records = adaptive_diagnosis_memory.build_learning_records(
        _diagnosis_payload(), learned_at_utc="2026-05-05T00:00:00Z"
    )

    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == "sdetkit.adaptive_diagnosis.learning_record.v1"
    assert record["source"] == "adaptive_diagnosis"
    assert record["source_status"] == "needs_fix"
    assert record["source_risk_score"] == 53
    assert record["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert record["signal"] == "formatting-drift-after-green-tests"
    assert record["recommended_fix"] == "Run ruff format on touched files."
    assert record["proof_command"].startswith("PYTHONPATH=src python -m ruff")
    assert record["repeat_count"] == 2
    assert record["affected_files"] == ["tests/test_case.py"]
    assert record["matched_signals"] == ["ruff-format-failure", "explicit-failed"]
    assert record["candidate_scenarios"] == ["RUFF_FORMAT_DRIFT", "PRE_COMMIT_HOOK_FAILURE"]
    assert record["selected_primary_diagnosis"] is True
    assert record["recommended_checks"] == ["Run ruff format on touched files."]
    assert record["proof_commands"] == [
        "PYTHONPATH=src python -m ruff format --check <touched-python-files>"
    ]
    assert record["proof_passed"] is None
    assert record["fix_accepted"] is None
    assert record["false_positive"] is False
    assert record["lane"] == "quality"
    assert record["learned_at_utc"] == "2026-05-05T00:00:00Z"
    assert len(record["record_id"]) == 16


def test_monitor_status_is_skipped_unless_requested():
    skipped = adaptive_diagnosis_memory.build_learning_records(_diagnosis_payload("monitor"))
    included = adaptive_diagnosis_memory.build_learning_records(
        _diagnosis_payload("monitor"), include_monitor=True
    )

    assert skipped == []
    assert len(included) == 1
    assert included[0]["source_status"] == "monitor"


def test_append_learning_records_deduplicates_by_record_id(tmp_path):
    db_path = tmp_path / "memory.jsonl"
    records = adaptive_diagnosis_memory.build_learning_records(
        _diagnosis_payload(), learned_at_utc="2026-05-05T00:00:00Z"
    )

    first = adaptive_diagnosis_memory.append_learning_records(db_path, records)
    second = adaptive_diagnosis_memory.append_learning_records(db_path, records)

    assert first["appended_records"] == 1
    assert first["total_records"] == 1
    assert second["appended_records"] == 0
    assert second["total_records"] == 1
    assert len(db_path.read_text(encoding="utf-8").splitlines()) == 1


def test_learn_from_diagnosis_writes_jsonl_summary(tmp_path):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    db_path = tmp_path / "memory" / "diagnosis.jsonl"
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")

    summary = adaptive_diagnosis_memory.learn_from_diagnosis(
        diagnosis_path,
        db_path,
        learned_at_utc="2026-05-05T00:00:00Z",
    )

    assert summary["ok"] is True
    assert summary["source_status"] == "needs_fix"
    assert summary["appended_records"] == 1
    row = json.loads(db_path.read_text(encoding="utf-8").strip())
    assert row["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert row["proof_command"]


def test_cli_writes_summary_and_rejects_bad_schema(tmp_path, capsys):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    db_path = tmp_path / "memory.jsonl"
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")

    rc = adaptive_diagnosis_memory.main(
        [str(diagnosis_path), "--db", str(db_path), "--format", "json"]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["appended_records"] == 1
    assert db_path.exists()

    diagnosis_path.write_text(json.dumps({"schema_version": "bad"}), encoding="utf-8")
    rc = adaptive_diagnosis_memory.main([str(diagnosis_path), "--db", str(db_path)])

    assert rc == 2
    assert "unsupported adaptive diagnosis schema" in capsys.readouterr().out


def test_learning_summary_shows_recurring_scenarios_and_weakest_lanes(tmp_path):
    db_path = tmp_path / "memory.jsonl"
    records = adaptive_diagnosis_memory.build_learning_records(
        _diagnosis_payload(), learned_at_utc="2026-05-05T00:00:00Z"
    )
    adaptive_diagnosis_memory.append_learning_records(db_path, records)

    summary = adaptive_diagnosis_memory.learning_summary_from_db(db_path)

    assert summary["schema_version"] == "sdetkit.adaptive.learn.summary.v1"
    assert summary["diagnosis_records"] == 1
    assert summary["top_recurring_scenarios"][0]["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert summary["top_recurring_scenarios"][0]["recurrence_count"] == 2
    assert summary["weakest_lanes"][0]["lane"] == "quality"
    assert summary["weakest_lanes"][0]["scenario_codes"] == ["PRE_COMMIT_FORMAT_DRIFT"]


def test_summarize_cli_outputs_learning_summary(tmp_path, capsys):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    db_path = tmp_path / "memory.jsonl"
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")
    assert adaptive_diagnosis_memory.main([str(diagnosis_path), "--db", str(db_path)]) == 0
    capsys.readouterr()

    rc = adaptive_diagnosis_memory.main(["summarize", "--db", str(db_path), "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "sdetkit.adaptive.learn.summary.v1"
    assert payload["weakest_lanes"][0]["lane"] == "quality"


def test_learning_summary_calibrates_promotion_and_risk_from_outcomes():
    payload = _diagnosis_payload()
    payload["diagnoses"][0]["repeat_count"] = 3
    records = adaptive_diagnosis_memory.build_learning_records(
        payload,
        learned_at_utc="2026-05-05T00:00:00Z",
        proof_passed=True,
        fix_accepted=True,
    )

    summary = adaptive_diagnosis_memory.summarize_learning_records(records)
    scenario = summary["top_recurring_scenarios"][0]

    assert scenario["proof_passed_count"] == 1
    assert scenario["fix_accepted_count"] == 1
    assert scenario["calibration"]["primary_action"] == "promote_and_increase_risk"
    assert scenario["calibration"]["calibrated_confidence"] == "high"
    assert scenario["calibration"]["risk_delta"] > 0
    assert "promote" in scenario["calibration"]["actions"]
    assert summary["calibration_summary"] == {
        "promote": 1,
        "demote": 0,
        "increase_risk": 1,
        "lower_confidence": 0,
    }


def test_learning_summary_demotes_false_positive_and_lowers_thin_evidence():
    payload = _diagnosis_payload()
    payload["diagnoses"][0]["evidence"] = ["custom tool failed without classifier context"]
    records = adaptive_diagnosis_memory.build_learning_records(
        payload,
        learned_at_utc="2026-05-05T00:00:00Z",
        proof_passed=False,
        fix_accepted=False,
        false_positive=True,
    )

    summary = adaptive_diagnosis_memory.summarize_learning_records(records)
    scenario = summary["top_recurring_scenarios"][0]

    assert scenario["false_positive_count"] == 1
    assert scenario["proof_failed_count"] == 1
    assert scenario["fix_rejected_count"] == 1
    assert scenario["calibration"]["primary_action"] == "demote"
    assert scenario["calibration"]["calibrated_confidence"] == "low"
    assert "lower_confidence" in scenario["calibration"]["actions"]
    assert summary["calibration_summary"]["demote"] == 1
    assert summary["calibration_summary"]["lower_confidence"] == 1


def test_cli_record_accepts_operator_outcome_flags(tmp_path, capsys):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    db_path = tmp_path / "memory.jsonl"
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")

    rc = adaptive_diagnosis_memory.main(
        [
            str(diagnosis_path),
            "--db",
            str(db_path),
            "--proof-passed",
            "--fix-accepted",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["appended_records"] == 1
    row = json.loads(db_path.read_text(encoding="utf-8").strip())
    assert row["proof_passed"] is True
    assert row["fix_accepted"] is True


def test_cli_rejects_conflicting_outcome_flags(tmp_path, capsys):
    diagnosis_path = tmp_path / "adaptive-diagnosis.json"
    db_path = tmp_path / "memory.jsonl"
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")

    rc = adaptive_diagnosis_memory.main(
        [
            str(diagnosis_path),
            "--db",
            str(db_path),
            "--proof-passed",
            "--proof-failed",
        ]
    )

    assert rc == 2
    assert "outcome flags are mutually exclusive" in capsys.readouterr().out
