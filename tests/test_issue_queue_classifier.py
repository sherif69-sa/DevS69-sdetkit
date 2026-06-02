from __future__ import annotations

import json
from pathlib import Path

from sdetkit.issue_queue_classifier import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    classify_issues,
    write_issue_queue_classifier_artifact,
)

FIXTURE = Path("tests/fixtures/issue_queue/sample-open-issues.json")


def _fixture_issues() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_issue_queue_classifier_emits_required_review_first_fields() -> None:
    payload = classify_issues(_fixture_issues())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["source_issue_count"] == 8
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False

    required = {
        "issue_number",
        "title",
        "state",
        "labels",
        "created_at",
        "updated_at",
        "classification",
        "priority_score",
        "roadmap_alignment",
        "blocking_status",
        "recommended_action",
        "proof_required_before_close",
        "linked_pr_or_none",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    }
    assert payload["issues"]
    assert all(required <= set(issue) for issue in payload["issues"])
    assert all(
        issue[field] is value
        for issue in payload["issues"]
        for field, value in AUTHORITY_BOUNDARY.items()
    )


def test_issue_queue_classifier_classifies_active_maintenance_lanes() -> None:
    payload = classify_issues(_fixture_issues())
    by_number = {issue["issue_number"]: issue for issue in payload["issues"]}

    assert by_number[1502]["classification"] == "security_followup"
    assert by_number[1502]["blocking_status"] == "possible_blocker_needs_security_review"
    assert by_number[1500]["classification"] == "generated_tracker"
    assert by_number[1500]["recommended_action"] == "keep_open_as_command_center"
    assert by_number[1518]["classification"] == "workflow_governance"
    assert by_number[1519]["classification"] == "docs_operator_gap"
    assert by_number[1504]["classification"] == "automation_health_gap"
    assert by_number[1505]["classification"] == "product_roadmap_gap"
    assert by_number[1517]["classification"] == "security_followup"
    assert by_number[1497]["classification"] == "security_followup"


def test_issue_queue_classifier_recommends_highest_priority_non_tracker() -> None:
    payload = classify_issues(_fixture_issues())

    assert payload["recommended_next_issue"] == 1502
    assert (
        payload["recommended_next_action"]
        == "review_current_security_evidence_then_open_scoped_fix_or_disposition_pr"
    )
    assert payload["classification_counts"]["security_followup"] == 3


def test_issue_queue_classifier_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "issue-queue-classifier.json"

    payload = write_issue_queue_classifier_artifact(issues_json=FIXTURE, out=out)

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
