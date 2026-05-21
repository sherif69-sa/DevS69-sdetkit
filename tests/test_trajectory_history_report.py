from __future__ import annotations

import json
from pathlib import Path

from sdetkit.trajectory_history_report import (
    build_history_summary,
    main,
    render_history_markdown,
)


def _records() -> list[dict]:
    return [
        {
            "trajectory_id": "t1",
            "diagnostic_id": "formatting-autopilot",
            "action": "run_pre_commit",
            "commit_sha": "abc123",
            "pr_number": 1388,
            "diagnosis": {
                "failure_class": "pre_commit_format_drift",
                "risk_surface": "quality",
            },
            "decision": {
                "review_first": False,
                "auto_fix_allowed": True,
            },
            "final_result": "safe_fix_candidate",
        },
        {
            "trajectory_id": "t2",
            "diagnostic_id": "pr-quality-evidence-signal-evidence-review-signal",
            "action": "review",
            "commit_sha": "def456",
            "pr_number": 1389,
            "diagnosis": {
                "failure_class": "evidence_review_signal",
                "risk_surface": "pr_quality",
            },
            "decision": {
                "review_first": True,
                "auto_fix_allowed": False,
            },
            "final_result": "evidence_review_required",
        },
        {
            "trajectory_id": "t3",
            "diagnostic_id": "release-review",
            "action": "review_release_failure",
            "commit_sha": "ghi789",
            "pr_number": 1390,
            "diagnosis": {
                "failure_class": "release_artifact_invalid",
                "risk_surface": "release",
            },
            "decision": {
                "review_first": True,
                "auto_fix_allowed": False,
            },
            "final_result": "review_required",
        },
    ]


def test_history_summary_counts_final_results_surfaces_and_decisions() -> None:
    summary = build_history_summary(_records(), recent_limit=2)

    assert summary["schema_version"] == "sdetkit.trajectory_history_report.v1"
    assert summary["record_count"] == 3
    assert summary["review_first_count"] == 2
    assert summary["auto_fix_allowed_count"] == 1
    assert summary["by_final_result"] == {
        "evidence_review_required": 1,
        "review_required": 1,
        "safe_fix_candidate": 1,
    }
    assert summary["by_risk_surface"] == {
        "pr_quality": 1,
        "quality": 1,
        "release": 1,
    }
    assert summary["by_action"] == {
        "review": 1,
        "review_release_failure": 1,
        "run_pre_commit": 1,
    }
    assert [item["diagnostic_id"] for item in summary["recent_decisions"]] == [
        "release-review",
        "pr-quality-evidence-signal-evidence-review-signal",
    ]


def test_history_markdown_renders_operator_summary() -> None:
    summary = build_history_summary(_records(), recent_limit=1)
    markdown = render_history_markdown(summary)

    assert "# Trajectory history summary" in markdown
    assert "Records: `3`" in markdown
    assert "Review-first decisions: `2`" in markdown
    assert "Auto-fix allowed decisions: `1`" in markdown
    assert "`evidence_review_required`: `1`" in markdown
    assert "`release`: `1`" in markdown
    assert "## Recent decisions" in markdown
    assert "`release-review`: action=`review_release_failure`" in markdown


def test_history_report_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    trajectory_path = tmp_path / "trajectory.jsonl"
    json_out = tmp_path / "summary.json"
    markdown_out = tmp_path / "summary.md"
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
            "--recent-limit",
            "2",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["summary"]["record_count"] == 3
    assert json.loads(json_out.read_text(encoding="utf-8"))["review_first_count"] == 2
    assert "Trajectory history summary" in markdown_out.read_text(encoding="utf-8")


def test_history_report_cli_accepts_multiple_jsonl_files(tmp_path: Path, capsys) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(json.dumps(_records()[0], sort_keys=True) + "\n", encoding="utf-8")
    second.write_text(json.dumps(_records()[1], sort_keys=True) + "\n", encoding="utf-8")

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
    assert printed["summary"]["record_count"] == 2
    assert printed["summary"]["review_first_count"] == 1
    assert printed["summary"]["auto_fix_allowed_count"] == 1
