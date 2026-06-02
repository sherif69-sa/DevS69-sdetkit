from __future__ import annotations

import json
from pathlib import Path

from sdetkit.security_followup_disposition import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_security_followup_disposition,
    write_security_followup_disposition_artifact,
)

ISSUES = Path("tests/fixtures/issue_queue/sample-open-issues.json")
WARN_SECURITY = Path("tests/fixtures/security_followup/security-check-warn.json")
CLEAN_SECURITY = Path("tests/fixtures/security_followup/security-check-clean.json")


def _issues() -> list[dict]:
    return json.loads(ISSUES.read_text(encoding="utf-8"))


def _security(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_security_followup_disposition_emits_review_first_boundary_fields() -> None:
    payload = build_security_followup_disposition(_issues(), _security(WARN_SECURITY))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "review required"
    assert payload["source_issue_count"] == 8
    assert payload["security_followup_count"] >= 3
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False

    required = {
        "issue_number",
        "title",
        "claimed_actionable_findings",
        "security_error_count",
        "security_warn_count",
        "current_finding_count",
        "new_finding_count",
        "disposition",
        "review_required",
        "close_candidate",
        "recommended_action",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    }
    assert payload["dispositions"]
    assert all(required <= set(item) for item in payload["dispositions"])
    assert all(
        item[field] is value
        for item in payload["dispositions"]
        for field, value in AUTHORITY_BOUNDARY.items()
    )


def test_security_followup_disposition_keeps_1502_review_required_when_warnings_exist() -> None:
    payload = build_security_followup_disposition(_issues(), _security(WARN_SECURITY))
    by_number = {item["issue_number"]: item for item in payload["dispositions"]}

    assert payload["primary_issue"] == 1502
    assert by_number[1502]["claimed_actionable_findings"] == 29
    assert by_number[1502]["security_warn_count"] == 29
    assert by_number[1502]["disposition"] == "needs review"
    assert by_number[1502]["review_required"] is True
    assert by_number[1502]["close_candidate"] is False
    assert (
        by_number[1502]["recommended_action"]
        == "review current security warnings and record a human disposition"
    )


def test_security_followup_disposition_marks_clean_snapshot_ready_with_proof() -> None:
    payload = build_security_followup_disposition(_issues(), _security(CLEAN_SECURITY))
    by_number = {item["issue_number"]: item for item in payload["dispositions"]}

    assert payload["status"] == "ready with proof"
    assert payload["primary_issue"] == 1502
    assert by_number[1502]["disposition"] == "ready with proof"
    assert by_number[1502]["review_required"] is False
    assert by_number[1502]["close_candidate"] is True
    assert (
        payload["recommended_next_action"]
        == "attach clean security proof before closing the follow up"
    )


def test_security_followup_disposition_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "security-followup-disposition.json"

    payload = write_security_followup_disposition_artifact(
        issues_json=ISSUES,
        security_json=WARN_SECURITY,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
