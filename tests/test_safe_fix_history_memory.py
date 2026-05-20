from __future__ import annotations

import json
from pathlib import Path

from sdetkit.safe_fix_history_memory import build_safe_fix_history, persist_safe_fix_history


def test_safe_fix_history_memory_merges_rollup_and_counts_trends() -> None:
    previous = {
        "attempts": [
            {
                "timestamp": "2026-05-01T00:00:00Z",
                "status": "pushed",
                "classification": "format_only",
                "head_sha": "aaa111",
                "affected_files": ["src/sdetkit/foo.py"],
                "format_drift": True,
                "committed": True,
                "pushed": True,
            }
        ]
    }
    rollup = {
        "safe_fix_outcomes": [
            {
                "timestamp": "2026-05-01T00:00:00Z",
                "head_sha": "aaa111",
                "status": "pushed",
                "fix_type": "format_only",
                "affected_files": ["src/sdetkit/foo.py"],
                "safe_fix_committed": True,
                "safe_fix_pushed": True,
            },
            {
                "timestamp": "2026-05-10T00:00:00Z",
                "head_sha": "bbb222",
                "attempted": True,
                "committed": True,
                "fix_type": "format_only",
                "affected_files": ["src/sdetkit/foo.py"],
            },
            {
                "timestamp": "2026-04-01T00:00:00Z",
                "head_sha": "ccc333",
                "safe_to_auto_fix": False,
                "classification": "runtime",
                "refused_reason": "runtime failures remain review-first",
                "review_first": True,
            },
        ]
    }

    history, trends, markdown = build_safe_fix_history(
        rollup,
        previous,
        observed_at="2026-05-20T00:00:00Z",
        source_path="build/operator-loop/safe-fix-outcome-rollup.json",
    )

    metrics = trends["metrics"]
    assert history["schema_version"] == "sdetkit.safe_fix_history_memory.v1"
    assert trends["schema_version"] == "sdetkit.safe_fix_trends.v1"
    assert metrics["safe_fix_attempts_total"] == 3
    assert metrics["safe_fix_attempts_last_30_days"] == 2
    assert metrics["safe_fix_pushed_total"] == 1
    assert metrics["safe_fix_committed_total"] == 2
    assert metrics["safe_fix_refused_total"] == 1
    assert metrics["safe_fix_success_rate"] == 0.6667
    assert metrics["recurring_format_drift_files"] == [{"file": "src/sdetkit/foo.py", "count": 2}]
    assert metrics["most_recent_safe_fix_status"] == "committed"
    assert "Safe-Fix History" in markdown


def test_safe_fix_history_memory_recommends_diagnosis_when_unknown_refusals_recur() -> None:
    rollup = {
        "outcomes": [
            {
                "timestamp": "2026-05-10T00:00:00Z",
                "safe_to_auto_fix": False,
                "classification": "unknown",
                "refused_reason": "unknown failures block safe mutation",
            },
            {
                "timestamp": "2026-05-11T00:00:00Z",
                "safe_to_auto_fix": False,
                "classification": "unknown",
                "refused_reason": "unknown failures block safe mutation",
            },
        ]
    }

    _, trends, _ = build_safe_fix_history(
        rollup,
        observed_at="2026-05-20T00:00:00Z",
    )

    metrics = trends["metrics"]
    assert metrics["safe_fix_refused_total"] == 2
    assert metrics["recurring_refusal_reasons"] == [
        {"reason": "unknown failures block safe mutation", "count": 2}
    ]
    assert (
        metrics["recommended_next_operator_action"]
        == "improve_failure_classification_before_any_mutation"
    )


def test_safe_fix_history_memory_recommends_guardrail_for_recurring_format_drift() -> None:
    rollup = {
        "outcomes": [
            {
                "timestamp": "2026-05-10T00:00:00Z",
                "status": "pushed",
                "classification": "format_only",
                "affected_files": ["src/sdetkit/repeated.py"],
                "pushed": True,
            },
            {
                "timestamp": "2026-05-11T00:00:00Z",
                "status": "committed",
                "classification": "format_only",
                "affected_files": ["src/sdetkit/repeated.py"],
                "committed": True,
            },
        ]
    }

    _, trends, _ = build_safe_fix_history(
        rollup,
        observed_at="2026-05-20T00:00:00Z",
    )

    metrics = trends["metrics"]
    assert metrics["recurring_format_drift_files"] == [
        {"file": "src/sdetkit/repeated.py", "count": 2}
    ]
    assert (
        metrics["recommended_next_operator_action"]
        == "add_local_guardrail_for_recurring_format_drift_files"
    )


def test_safe_fix_history_memory_writes_json_and_markdown_artifacts(tmp_path: Path) -> None:
    rollup_path = tmp_path / "safe-fix-outcome-rollup.json"
    rollup_path.write_text(
        json.dumps(
            {
                "attempted": True,
                "committed": True,
                "pushed": True,
                "timestamp": "2026-05-19T00:00:00Z",
                "fix_type": "format_only",
                "affected_files": ["src/sdetkit/bar.py"],
            }
        ),
        encoding="utf-8",
    )

    paths = persist_safe_fix_history(
        rollup_path,
        tmp_path / "safe-fix-history",
        observed_at="2026-05-20T00:00:00Z",
    )

    history = json.loads(paths["history_json"].read_text(encoding="utf-8"))
    trends = json.loads(paths["trends_json"].read_text(encoding="utf-8"))
    markdown = paths["history_md"].read_text(encoding="utf-8")

    assert paths["history_json"].name == "safe-fix-history.json"
    assert paths["trends_json"].name == "safe-fix-trends.json"
    assert paths["history_md"].name == "safe-fix-history.md"
    assert history["metrics"]["safe_fix_attempts_total"] == 1
    assert trends["metrics"]["safe_fix_success_rate"] == 1.0
    assert "Recommended next operator action" in markdown


def test_safe_fix_history_memory_emits_owner_file_guardrail_advice() -> None:
    from sdetkit.safe_fix_history_memory import build_safe_fix_history

    _, trends, _ = build_safe_fix_history(
        {
            "outcomes": [
                {
                    "timestamp": "2026-05-10T00:00:00Z",
                    "status": "pushed",
                    "classification": "format_only",
                    "affected_files": ["src/sdetkit/operator_brief.py"],
                    "pushed": True,
                },
                {
                    "timestamp": "2026-05-11T00:00:00Z",
                    "status": "committed",
                    "classification": "format_only",
                    "affected_files": ["src/sdetkit/operator_brief.py"],
                    "committed": True,
                },
            ]
        },
        observed_at="2026-05-20T00:00:00Z",
    )

    metrics = trends["metrics"]

    assert metrics["format_drift_owner_files"] == [
        {
            "file": "src/sdetkit/operator_brief.py",
            "count": 2,
            "owner_signal": "recurring_format_drift",
        }
    ]
    assert metrics["owner_file_guardrail_recommendations"] == [
        {
            "file": "src/sdetkit/operator_brief.py",
            "count": 2,
            "action": "add_owner_file_format_guardrail",
            "reason": "file repeatedly required deterministic formatting safe fixes",
        }
    ]
    assert metrics["local_dev_guardrail_recommendations"] == [
        {
            "file": "src/sdetkit/operator_brief.py",
            "count": 2,
            "action": "run_pre_commit_before_push",
            "reason": "recurring format drift should be caught before CI",
        }
    ]
    assert metrics["recurring_format_drift_guardrails"] == []
    assert (
        metrics["recommended_next_operator_action"]
        == "add_local_guardrail_for_recurring_format_drift_files"
    )


def test_safe_fix_history_memory_escalates_three_time_recurring_format_drift() -> None:
    from sdetkit.safe_fix_history_memory import build_safe_fix_history

    _, trends, markdown = build_safe_fix_history(
        {
            "outcomes": [
                {
                    "timestamp": "2026-05-10T00:00:00Z",
                    "status": "pushed",
                    "classification": "format_only",
                    "affected_files": ["tools/maintenance_autopilot.py"],
                    "pushed": True,
                },
                {
                    "timestamp": "2026-05-11T00:00:00Z",
                    "status": "committed",
                    "classification": "format_only",
                    "affected_files": ["tools/maintenance_autopilot.py"],
                    "committed": True,
                },
                {
                    "timestamp": "2026-05-12T00:00:00Z",
                    "status": "pushed",
                    "classification": "format_only",
                    "affected_files": ["tools/maintenance_autopilot.py"],
                    "pushed": True,
                },
            ]
        },
        observed_at="2026-05-20T00:00:00Z",
    )

    metrics = trends["metrics"]

    assert metrics["recurring_format_drift_guardrails"] == [
        {
            "file": "tools/maintenance_autopilot.py",
            "count": 3,
            "action": "escalate_recurring_format_drift",
            "reason": "same file crossed recurring drift escalation threshold",
        }
    ]
    assert (
        metrics["recommended_next_operator_action"] == "escalate_recurring_format_drift_guardrails"
    )
    assert "Owner-file guardrail recommendations" in markdown
    assert "Local developer guardrail recommendations" in markdown
    assert "Recurring format drift guardrails" in markdown
