from __future__ import annotations

import json
from pathlib import Path

from sdetkit.automation_health import build_automation_health
from sdetkit.issue_queue_classifier import classify_issues
from sdetkit.maintenance_queue_rollup import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_maintenance_queue_rollup,
    write_maintenance_queue_rollup_artifact,
)
from sdetkit.security_followup_disposition import build_security_followup_disposition

ISSUES = Path("tests/fixtures/issue_queue/sample-open-issues.json")
WARN_SECURITY = Path("tests/fixtures/security_followup/security-check-warn.json")


def _issues() -> list[dict]:
    return json.loads(ISSUES.read_text(encoding="utf-8"))


def _warn_security() -> dict:
    return json.loads(WARN_SECURITY.read_text(encoding="utf-8"))


def _payloads() -> tuple[dict, dict, dict]:
    issues = _issues()
    issue_queue = classify_issues(issues)
    automation_health = build_automation_health(issues)
    security_followup = build_security_followup_disposition(issues, _warn_security())
    return issue_queue, automation_health, security_followup


def test_maintenance_queue_rollup_emits_review_first_boundary_fields() -> None:
    issue_queue, automation_health, security_followup = _payloads()

    payload = build_maintenance_queue_rollup(issue_queue, automation_health, security_followup)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "review required"
    assert payload["queue_item_count"] == 8
    assert payload["review_required_count"] >= 1
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False

    required = {
        "issue_number",
        "title",
        "lane",
        "classification",
        "rank_score",
        "review_required",
        "close_candidate",
        "security_disposition",
        "automation_health_state",
        "recommended_action",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    }
    assert payload["queue_items"]
    assert all(required <= set(item) for item in payload["queue_items"])
    assert all(
        item[field] is value
        for item in payload["queue_items"]
        for field, value in AUTHORITY_BOUNDARY.items()
    )


def test_maintenance_queue_rollup_prioritizes_1502_security_review() -> None:
    issue_queue, automation_health, security_followup = _payloads()

    payload = build_maintenance_queue_rollup(issue_queue, automation_health, security_followup)
    by_number = {item["issue_number"]: item for item in payload["queue_items"]}

    assert payload["primary_issue"] == 1502
    assert by_number[1502]["lane"] == "security"
    assert by_number[1502]["review_required"] is True
    assert by_number[1502]["close_candidate"] is False
    assert by_number[1502]["security_disposition"] == "needs review"
    assert (
        payload["recommended_next_action"]
        == "review current security warnings and record a human disposition"
    )


def test_maintenance_queue_rollup_keeps_generated_trackers_non_primary_context() -> None:
    issue_queue, automation_health, security_followup = _payloads()

    payload = build_maintenance_queue_rollup(issue_queue, automation_health, security_followup)
    by_number = {item["issue_number"]: item for item in payload["queue_items"]}

    assert by_number[1500]["lane"] == "command center"
    assert by_number[1500]["close_candidate"] is True
    assert by_number[1500]["review_required"] is False
    assert payload["primary_issue"] != 1500


def test_maintenance_queue_rollup_writes_artifact(tmp_path: Path) -> None:
    issue_queue, automation_health, security_followup = _payloads()
    issue_queue_path = tmp_path / "issue-queue.json"
    automation_path = tmp_path / "automation-health.json"
    security_path = tmp_path / "security-followup.json"
    out = tmp_path / "maintenance-queue-rollup.json"

    issue_queue_path.write_text(json.dumps(issue_queue), encoding="utf-8")
    automation_path.write_text(json.dumps(automation_health), encoding="utf-8")
    security_path.write_text(json.dumps(security_followup), encoding="utf-8")

    payload = write_maintenance_queue_rollup_artifact(
        issue_queue_json=issue_queue_path,
        automation_health_json=automation_path,
        security_followup_json=security_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
