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


def test_pattern_insights_summarizes_safety_gate_evidence() -> None:
    rows = _records()[:1]
    rows[0]["safety_gate"] = {
        "source": "failure_bundle.safety_summary",
        "review_first": False,
        "safe_fix_allowed": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "report_path": "build/pr-quality/failure-bundle/failure-bundle.md",
    }

    insights = build_pattern_insights(rows, minimum_repeat=1)
    safety_gate = insights["safety_gate_evidence"]

    assert safety_gate["collection_status"] == "collected"
    assert safety_gate["status"] == "safety_gate_evidence_observed"
    assert safety_gate["record_count"] == 1
    assert safety_gate["safe_fix_allowed_count"] == 1
    assert safety_gate["review_first_count"] == 0
    assert safety_gate["reporting_only_count"] == 1
    assert safety_gate["report_paths"] == ["build/pr-quality/failure-bundle/failure-bundle.md"]
    assert safety_gate["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    markdown = render_pattern_markdown(insights)
    assert "## SafetyGate evidence" in markdown
    assert "Safe-fix allowed records: `1`" in markdown
    assert "Automation allowed by SafetyGate evidence: `false`" in markdown


def test_pattern_insights_summarizes_trajectory_authority_boundary_evidence() -> None:
    rows = _records()[:2]
    rows[0]["authority_boundary"] = {
        "source": "pr_quality",
        "reporting_only": True,
        "review_first": True,
        "auto_fix_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }
    rows[1]["authority_boundary"] = {
        "source": "trajectory_store",
        "reporting_only": True,
        "review_first": False,
        "auto_fix_allowed": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    insights = build_pattern_insights(rows, minimum_repeat=1)
    authority = insights["authority_boundary_evidence"]

    assert authority["collection_status"] == "collected"
    assert authority["status"] == "authority_boundary_evidence_observed"
    assert authority["record_count"] == 2
    assert authority["review_first_count"] == 1
    assert authority["auto_fix_allowed_count"] == 1
    assert authority["reporting_only_count"] == 2
    assert authority["sources"] == ["pr_quality", "trajectory_store"]
    assert authority["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    markdown = render_pattern_markdown(insights)
    assert "## Trajectory authority boundary evidence" in markdown
    assert "Auto-fix evidence records: `1`" in markdown
    assert "Security dismissal allowed by trajectory authority evidence: `false`" in markdown


def test_pattern_insights_summarizes_failure_vector_contract_evidence() -> None:
    rows = _records()[:1]
    rows[0]["failure_vector_contract"] = {
        "source": "failure_vector.contract",
        "schema_version": "sdetkit.failure_vector.contract.v1",
        "failure_kind": "test",
        "affected_surface": "tests",
        "ownership_area": "tests/test_widget.py",
        "retryability": "not_retryable_without_change",
        "security_relevance": False,
        "recommended_next_human_action": "inspect failing test and affected file",
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
        "authority_boundary_preserved": True,
    }

    insights = build_pattern_insights(rows, minimum_repeat=1)
    evidence = insights["failure_vector_contract_evidence"]

    assert evidence["collection_status"] == "collected"
    assert evidence["status"] == "failure_vector_contract_evidence_observed"
    assert evidence["record_count"] == 1
    assert evidence["security_relevance_count"] == 0
    assert evidence["authority_boundary_preserved_count"] == 1
    assert evidence["failure_kinds"] == [{"value": "test", "count": 1}]
    assert evidence["affected_surfaces"] == [{"value": "tests", "count": 1}]
    assert evidence["decision_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_claim": False,
    }

    markdown = render_pattern_markdown(insights)
    assert "## FailureVector contract evidence" in markdown
    assert "Authority boundary preserved records: `1`" in markdown
    assert "Security dismissal allowed by FailureVector contract evidence: `false`" in markdown
