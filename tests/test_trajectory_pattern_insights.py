from __future__ import annotations

import json
from pathlib import Path

from sdetkit.trajectory_pattern_insights import (
    build_pattern_insights,
    main,
    render_pattern_markdown,
)


def _records() -> list[dict]:
    return [
        {
            "trajectory_id": "t1",
            "diagnostic_id": "evidence-review-1",
            "action": "review",
            "diagnosis": {
                "failure_class": "evidence_review_signal",
                "risk_surface": "pr_quality",
            },
            "decision": {"review_first": True, "auto_fix_allowed": False},
            "final_result": "evidence_review_required",
        },
        {
            "trajectory_id": "t2",
            "diagnostic_id": "evidence-review-2",
            "action": "review",
            "diagnosis": {
                "failure_class": "evidence_review_signal",
                "risk_surface": "pr_quality",
            },
            "decision": {"review_first": True, "auto_fix_allowed": False},
            "final_result": "evidence_review_required",
        },
        {
            "trajectory_id": "t3",
            "diagnostic_id": "release-review",
            "action": "review_release_failure",
            "diagnosis": {
                "failure_class": "release_artifact_invalid",
                "risk_surface": "release",
            },
            "decision": {"review_first": True, "auto_fix_allowed": False},
            "final_result": "review_required",
        },
        {
            "trajectory_id": "t4",
            "diagnostic_id": "format-fix-1",
            "action": "run_pre_commit",
            "diagnosis": {
                "failure_class": "pre_commit_format_drift",
                "risk_surface": "quality",
            },
            "decision": {"review_first": False, "auto_fix_allowed": True},
            "final_result": "safe_fix_candidate",
        },
        {
            "trajectory_id": "t5",
            "diagnostic_id": "format-fix-2",
            "action": "run_pre_commit",
            "diagnosis": {
                "failure_class": "pre_commit_format_drift",
                "risk_surface": "quality",
            },
            "decision": {"review_first": False, "auto_fix_allowed": True},
            "final_result": "safe_fix_candidate",
        },
    ]


def test_pattern_insights_find_repeated_review_and_safe_fix_signals() -> None:
    insights = build_pattern_insights(_records(), minimum_repeat=2)

    assert insights["schema_version"] == "sdetkit.trajectory_pattern_insights.v1"
    assert insights["record_count"] == 5
    assert insights["history_summary"]["review_first_count"] == 3
    assert insights["history_summary"]["auto_fix_allowed_count"] == 2
    assert insights["dominant_risk_surface"]["value"] == "pr_quality"
    assert insights["dominant_risk_surface"]["count"] == 2
    assert insights["dominant_action"]["value"] == "review"
    assert insights["recurring_review_first_surfaces"] == [{"value": "pr_quality", "count": 2}]
    assert insights["recurring_safe_fix_patterns"] == [
        {
            "failure_class": "pre_commit_format_drift",
            "action": "run_pre_commit",
            "count": 2,
        }
    ]
    assert insights["operator_focus"]["priority"] == "review_first_recurrence"
    assert insights["operator_focus"]["surface"] == "pr_quality"


def test_pattern_insights_does_not_claim_recurrence_from_one_record() -> None:
    insights = build_pattern_insights(_records()[:1], minimum_repeat=2)

    assert insights["recurring_review_first_surfaces"] == []
    assert insights["recurring_safe_fix_patterns"] == []
    assert insights["operator_focus"]["priority"] == "review_first_observed"


def test_pattern_insights_rejects_invalid_repeat_threshold() -> None:
    try:
        build_pattern_insights(_records(), minimum_repeat=0)
    except ValueError as exc:
        assert "minimum_repeat must be at least 1" in str(exc)
    else:
        raise AssertionError("expected invalid repeat threshold to raise")


def test_pattern_markdown_renders_operator_focus() -> None:
    markdown = render_pattern_markdown(build_pattern_insights(_records()))

    assert "# Trajectory pattern insights" in markdown
    assert "Records analyzed: `5`" in markdown
    assert "## Recurring review-first surfaces" in markdown
    assert "`pr_quality`: `2`" in markdown
    assert "class=`pre_commit_format_drift`, action=`run_pre_commit`, count=`2`" in markdown
    assert "Priority: `review_first_recurrence`" in markdown


def test_pattern_insights_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    trajectory_path = tmp_path / "trajectory.jsonl"
    json_out = tmp_path / "insights.json"
    markdown_out = tmp_path / "insights.md"
    trajectory_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in _records()) + "\n",
        encoding="utf-8",
    )

    rc = main(
        [
            "--trajectory-jsonl",
            str(trajectory_path),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--minimum-repeat",
            "2",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")

    assert printed["insights"]["record_count"] == 5
    assert saved["operator_focus"]["priority"] == "review_first_recurrence"
    assert "Trajectory pattern insights" in markdown


def test_pattern_insights_cli_accepts_multiple_trajectory_files(
    tmp_path: Path,
    capsys,
) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in _records()[:3]) + "\n",
        encoding="utf-8",
    )
    second.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in _records()[3:]) + "\n",
        encoding="utf-8",
    )

    rc = main(
        [
            "--trajectory-jsonl",
            str(first),
            "--trajectory-jsonl",
            str(second),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["insights"]["record_count"] == 5
    assert printed["insights"]["recurring_review_first_surfaces"][0]["value"] == "pr_quality"
