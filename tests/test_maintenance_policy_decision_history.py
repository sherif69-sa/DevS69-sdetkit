import json

from sdetkit import maintenance_policy_decision_history as history


def _policy_decisions():
    return {
        "decision": "BLOCK_RELEASE",
        "ok": False,
        "release_blocking": True,
        "automation_allowed": False,
        "top_action": "Review maintenance check `lint_check`.",
        "top_reason": "Priority-1 maintenance failure was reported.",
        "top_adaptive_context": "Treat it as release-blocking.",
        "decisions": [
            {
                "rank": 1,
                "decision": "BLOCK_RELEASE",
                "priority": 1,
                "source": "maintenance",
                "severity": "error",
                "title": "Maintenance check failed: lint_check",
                "action": "Review maintenance check `lint_check`.",
                "reason": "Priority-1 maintenance failure was reported.",
                "adaptive_context": "Treat it as release-blocking.",
                "source_key": "maintenance:lint_check",
                "memory_lookup_key": "maintenance:lint_check",
                "confidence": "high",
                "automation_risk": "high",
                "review_risk": "high",
                "release_risk": "high",
                "policy_basis": ["source=maintenance", "priority=1"],
            },
            {
                "rank": 2,
                "decision": "TRACK_ONLY",
                "priority": 2,
                "source": "annotation_hygiene",
                "severity": "warning",
                "title": "GitHub Actions Node.js 20 runtime deprecation",
                "action": "Update the action or test Node 24.",
                "source_key": "annotation:node20:submit-pypi",
                "memory_lookup_key": "annotation:node20:submit-pypi",
                "confidence": "medium",
                "automation_risk": "high",
                "review_risk": "low",
                "release_risk": "low",
                "policy_basis": ["source=annotation_hygiene", "priority=2"],
            },
        ],
    }


def _memory_context():
    return {
        "memory_aware": True,
        "memory_enriched_count": 1,
        "repeated_signal_count": 1,
        "top_memory_context": "This signal has appeared 3 time(s).",
        "decisions": [
            {
                "memory_lookup_key": "annotation:node20:submit-pypi",
                "memory_enriched": True,
                "history_context": {
                    "matched": True,
                    "context_type": "history",
                    "seen_count": 3,
                    "decisions_by_type": {"TRACK_ONLY": 3},
                    "summary": "This signal has appeared 3 time(s).",
                    "policy_hint": "Escalate recurrence review if the same non-green decision keeps appearing.",
                },
                "annotation_context": {
                    "matched": True,
                    "context_type": "annotation_hygiene",
                    "finding_id": "github_actions_node20_deprecation",
                    "job": "submit-pypi",
                    "severity": "warning",
                    "summary": "Annotation memory matched node20.",
                    "policy_hint": "Track as workflow hygiene.",
                },
            }
        ],
    }


def test_build_history_record_compacts_policy_and_memory_context():
    record = history.build_history_record(
        _policy_decisions(),
        memory_context=_memory_context(),
        recorded_at_utc="2026-05-05T00:00:00Z",
        run_id="12345",
    )

    assert record["schema_version"] == "sdetkit.maintenance.policy_decision_history.v1"
    assert record["recorded_at_utc"] == "2026-05-05T00:00:00Z"
    assert record["run_id"] == "12345"
    assert record["decision"] == "BLOCK_RELEASE"
    assert record["release_blocking"] is True
    assert record["decision_count"] == 2
    assert record["memory_aware"] is True
    assert record["memory_enriched_count"] == 1
    assert record["repeated_signal_count"] == 1
    assert len(record["record_id"]) == 24

    by_key = {item["memory_lookup_key"]: item for item in record["decisions"]}
    node20 = by_key["annotation:node20:submit-pypi"]
    assert node20["memory_enriched"] is True
    assert node20["history_context"]["seen_count"] == 3
    assert node20["annotation_context"]["job"] == "submit-pypi"


def test_append_history_record_dedupes_by_record_id(tmp_path):
    path = tmp_path / "history" / "policy.jsonl"
    record = history.build_history_record(
        _policy_decisions(),
        recorded_at_utc="2026-05-05T00:00:00Z",
        run_id="run-1",
    )

    first = history.append_history_record(path, record)
    second = history.append_history_record(path, record)

    assert first["appended"] is True
    assert first["history_count"] == 1
    assert second["appended"] is False
    assert second["history_count"] == 1
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_render_markdown_summarizes_append_result(tmp_path):
    path = tmp_path / "policy-history.jsonl"
    record = history.build_history_record(_policy_decisions(), run_id="run-1")
    summary = history.append_history_record(path, record)

    rendered = history.render_markdown(summary)

    assert "# Maintenance policy decision history" in rendered
    assert "appended: **True**" in rendered
    assert "decision: **BLOCK_RELEASE**" in rendered
    assert "record id:" in rendered


def test_cli_appends_history_and_writes_outputs(tmp_path):
    policy_path = tmp_path / "policy.json"
    memory_path = tmp_path / "memory.json"
    history_path = tmp_path / "history.jsonl"
    out_json = tmp_path / "history-summary.json"
    out_md = tmp_path / "history-summary.md"

    policy_path.write_text(json.dumps(_policy_decisions()), encoding="utf-8")
    memory_path.write_text(json.dumps(_memory_context()), encoding="utf-8")

    rc = history.main(
        [
            "--policy-decisions-json",
            str(policy_path),
            "--memory-context-json",
            str(memory_path),
            "--history-jsonl",
            str(history_path),
            "--run-id",
            "run-1",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "md",
        ]
    )

    assert rc == 0
    summary = json.loads(out_json.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["appended"] is True
    assert summary["history_count"] == 1
    assert records[0]["memory_enriched_count"] == 1
    assert records[0]["decisions"][1]["history_context"]["seen_count"] == 3
    assert "Maintenance policy decision history" in out_md.read_text(encoding="utf-8")


def test_cli_allows_policy_decisions_without_memory_context(tmp_path):
    policy_path = tmp_path / "policy.json"
    history_path = tmp_path / "history.jsonl"

    policy_path.write_text(json.dumps(_policy_decisions()), encoding="utf-8")

    rc = history.main(
        [
            "--policy-decisions-json",
            str(policy_path),
            "--history-jsonl",
            str(history_path),
        ]
    )

    assert rc == 0
    records = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records[0]["memory_aware"] is False
    assert records[0]["memory_enriched_count"] == 0
