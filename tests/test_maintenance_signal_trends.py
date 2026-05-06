import json

from sdetkit import maintenance_signal_trends as trends


def _proof_payload():
    return {
        "schema_version": "sdetkit.maintenance.proof_checklist.v1",
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "items": [
            {
                "rank": 1,
                "signal": "Run ruff check",
                "memory_lookup_key": "diagnosis:RUFF_FIXABLE_LINT:lint",
                "diagnosis_class": "RUFF_FIXABLE_LINT",
                "category": "lint",
                "risk_level": "low",
                "safe_fix_route": "candidate_later",
                "proof_status": "missing",
            },
            {
                "rank": 2,
                "signal": "Run pytest -q",
                "memory_lookup_key": "diagnosis:PRODUCT_LOGIC_FAILURE:tests",
                "diagnosis_class": "PRODUCT_LOGIC_FAILURE",
                "category": "product_logic",
                "risk_level": "high",
                "safe_fix_route": "review_first",
                "proof_status": "missing",
            },
            {
                "rank": 3,
                "signal": "Unknown maintenance signal",
                "memory_lookup_key": "diagnosis:UNKNOWN_REVIEW_REQUIRED:unknown",
                "diagnosis_class": "UNKNOWN_REVIEW_REQUIRED",
                "category": "unknown",
                "risk_level": "medium",
                "safe_fix_route": "review_first",
                "proof_status": "missing",
            },
        ],
    }


def _history_records():
    return [
        {
            "run_id": "1",
            "decisions": [
                {
                    "memory_lookup_key": "diagnosis:PRODUCT_LOGIC_FAILURE:tests",
                    "decision": "REVIEW_REQUIRED",
                    "title": "Run pytest -q",
                }
            ],
        },
        {
            "run_id": "2",
            "decisions": [
                {
                    "memory_lookup_key": "diagnosis:PRODUCT_LOGIC_FAILURE:tests",
                    "decision": "REVIEW_REQUIRED",
                    "title": "Run pytest -q",
                }
            ],
        },
        {
            "run_id": "3",
            "decisions": [
                {
                    "memory_lookup_key": "diagnosis:PRODUCT_LOGIC_FAILURE:tests",
                    "decision": "REVIEW_REQUIRED",
                    "title": "Run pytest -q",
                },
                {
                    "memory_lookup_key": "diagnosis:UNKNOWN_REVIEW_REQUIRED:unknown",
                    "decision": "REVIEW_REQUIRED",
                    "title": "Unknown maintenance signal",
                },
            ],
        },
    ]


def _safe_fix_rollup():
    return {
        "schema_version": "sdetkit.adaptive.safe_fix_memory_rollup.v1",
        "groups": [
            {
                "fix_type": "ruff_fixable_lint",
                "code": "RUFF_FIXABLE_LINT",
                "remediation_attempts": 2,
                "remediation_successes": 2,
                "commit_pushes": 1,
                "latest_remediation_status": "success",
            }
        ],
    }


def test_build_signal_trends_uses_history_and_safe_fix_rollup():
    payload = trends.build_signal_trends(
        _proof_payload(),
        history_records=_history_records(),
        safe_fix_rollup=_safe_fix_rollup(),
    )

    assert payload["schema_version"] == "sdetkit.maintenance.signal_trends.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["signal_count"] == 3
    assert payload["repeated_signal_count"] == 1
    assert payload["prior_safe_fix_success_count"] == 1

    by_key = {item["memory_lookup_key"]: item for item in payload["signals"]}

    ruff = by_key["diagnosis:RUFF_FIXABLE_LINT:lint"]
    assert ruff["trend"] == "previously_fixed"
    assert ruff["safe_fix_attempts"] == 2
    assert ruff["safe_fix_successes"] == 2
    assert ruff["recommendation_impact"] == "candidate_later"

    product = by_key["diagnosis:PRODUCT_LOGIC_FAILURE:tests"]
    assert product["seen_count"] == 3
    assert product["recent_count"] == 1
    assert product["trend"] == "recurring"
    assert product["recommendation_impact"] == "prioritize_review"

    unknown = by_key["diagnosis:UNKNOWN_REVIEW_REQUIRED:unknown"]
    assert unknown["seen_count"] == 1
    assert unknown["trend"] == "new"
    assert unknown["recommendation_impact"] == "observe"


def test_empty_history_keeps_signals_new_and_diagnostic_only():
    payload = trends.build_signal_trends(_proof_payload())

    assert payload["automation_allowed"] is False
    assert payload["counts_by_trend"] == {"new": 3}
    assert all(item["trend"] == "new" for item in payload["signals"])


def test_render_markdown_is_comment_ready():
    payload = trends.build_signal_trends(
        _proof_payload(),
        history_records=_history_records(),
        safe_fix_rollup=_safe_fix_rollup(),
    )
    rendered = trends.render_markdown(payload)

    assert "# Maintenance signal trends" in rendered
    assert "automation allowed: **False**" in rendered
    assert "prior safe-fix successes: **1**" in rendered
    assert "Signal trends" in rendered
    assert "RUFF_FIXABLE_LINT" in rendered
    assert "previously_fixed" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    proof = tmp_path / "proof.json"
    history = tmp_path / "history.jsonl"
    rollup = tmp_path / "safe-fix-rollup.json"
    out_json = tmp_path / "trends.json"
    out_md = tmp_path / "trends.md"

    proof.write_text(json.dumps(_proof_payload()), encoding="utf-8")
    history.write_text(
        "\n".join(json.dumps(row) for row in _history_records()) + "\n",
        encoding="utf-8",
    )
    rollup.write_text(json.dumps(_safe_fix_rollup()), encoding="utf-8")

    rc = trends.main(
        [
            "--proof-checklist-json",
            str(proof),
            "--history-jsonl",
            str(history),
            "--safe-fix-rollup-json",
            str(rollup),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "md",
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.maintenance.signal_trends.v1"
    assert payload["prior_safe_fix_success_count"] == 1
    assert "Maintenance signal trends" in out_md.read_text(encoding="utf-8")
