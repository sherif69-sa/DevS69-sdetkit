from __future__ import annotations

import json
from pathlib import Path

from sdetkit.automation_health import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_automation_health,
    write_automation_health_artifact,
)

FIXTURE = Path("tests/fixtures/issue_queue/sample-open-issues.json")


def _fixture_issues() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_automation_health_emits_review_first_boundary_fields() -> None:
    payload = build_automation_health(_fixture_issues())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["source_issue_count"] == 8
    assert payload["automation_signal_count"] >= 5
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["input_issue_queue_schema_version"].startswith("sdetkit.issue_queue_classifier.")

    required = {
        "issue_number",
        "title",
        "lane",
        "classification",
        "health_state",
        "priority_score",
        "blocking_status",
        "recommended_action",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    }
    assert payload["automation_signals"]
    assert all(required <= set(signal) for signal in payload["automation_signals"])
    assert all(
        signal[field] is value
        for signal in payload["automation_signals"]
        for field, value in AUTHORITY_BOUNDARY.items()
    )


def test_automation_health_classifies_workflow_worker_and_security_lanes() -> None:
    payload = build_automation_health(_fixture_issues())
    by_number = {signal["issue_number"]: signal for signal in payload["automation_signals"]}

    assert by_number[1502]["lane"] == "security_automation"
    assert by_number[1502]["health_state"] == "possible_blocker_review_required"
    assert by_number[1504]["lane"] == "worker_alignment"
    assert by_number[1504]["health_state"] == "review_required"
    assert by_number[1518]["lane"] == "workflow_governance"
    assert by_number[1518]["health_state"] == "healthy_observed"
    assert by_number[1500]["lane"] == "command_center"
    assert by_number[1500]["recommended_action"] == "keep_open_as_queue_control_center"


def test_automation_health_recommends_security_autopilot_followup_first() -> None:
    payload = build_automation_health(_fixture_issues())

    assert payload["status"] == "review_required"
    assert payload["primary_signal_issue"] == 1502
    assert (
        payload["recommended_next_action"]
        == "review_current_automation_or_security_evidence_before_closing"
    )
    assert payload["health_state_counts"]["possible_blocker_review_required"] == 1
    assert payload["lane_counts"]["workflow_governance"] == 1


def test_automation_health_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "automation-health.json"

    payload = write_automation_health_artifact(issues_json=FIXTURE, out=out)

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
