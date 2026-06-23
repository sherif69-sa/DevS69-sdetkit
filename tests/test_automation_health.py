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


def test_automation_health_provenance_and_freshness_contract(
    tmp_path: Path,
    capsys,
) -> None:
    from sdetkit.automation_health import check_automation_health_freshness
    from sdetkit.cli import main as cli_main

    issues_path = tmp_path / "issues.json"
    issues_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "automation-health.json"

    payload = write_automation_health_artifact(
        issues_json=issues_path,
        out=out,
        root=".",
        source_run_ids=[202],
        generated_at="2026-06-23T00:00:00Z",
    )
    assert payload["schema_version"].endswith(".v2")
    assert payload["source_run_ids"] == [202]
    assert len(payload["current_head_sha"]) == 40
    assert payload["input_provenance"]["input_artifact_schemas"]["issue_queue_classifier"].endswith(
        ".v2"
    )
    assert "issue_queue_classifier_source" in payload["input_digests"]

    fresh = check_automation_health_freshness(
        issues_json=issues_path,
        report_path=out,
        root=".",
        source_run_ids=[202],
    )
    assert fresh["fresh"] is True
    assert fresh["reasons"] == []

    original = out.read_text(encoding="utf-8")
    rc = cli_main(
        [
            "automation-health",
            "--issues-json",
            str(issues_path),
            "--out",
            str(out),
            "--root",
            ".",
            "--source-run-id",
            "202",
            "--check-freshness",
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "freshness_status=fresh" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == original

    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    issues[0]["title"] = str(issues[0].get("title", "")) + " changed"
    issues_path.write_text(json.dumps(issues), encoding="utf-8")
    stale = check_automation_health_freshness(
        issues_json=issues_path,
        report_path=out,
        root=".",
        source_run_ids=[202],
    )
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]


def test_automation_health_freshness_rejects_missing_and_invalid_reports(
    tmp_path: Path,
) -> None:
    from sdetkit.automation_health import check_automation_health_freshness

    missing = check_automation_health_freshness(
        issues_json=FIXTURE,
        report_path=tmp_path / "missing.json",
        root=".",
    )
    assert "report_missing" in missing["reasons"]

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    result = check_automation_health_freshness(
        issues_json=FIXTURE,
        report_path=invalid,
        root=".",
    )
    assert "report_invalid_type" in result["reasons"]
