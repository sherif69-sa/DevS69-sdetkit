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
                "evidence": ["ruff-format modified files"],
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
