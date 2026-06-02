from __future__ import annotations

import json
from pathlib import Path

from sdetkit.security_findings_inventory import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_security_findings_inventory,
    write_security_findings_inventory_artifact,
)

WARN_SECURITY = Path("tests/fixtures/security_followup/security-check-warn.json")
CLEAN_SECURITY = Path("tests/fixtures/security_followup/security-check-clean.json")


def _security(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_security_findings_inventory_groups_findings_without_authority() -> None:
    payload = build_security_findings_inventory(_security(WARN_SECURITY))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "warnings need review"
    assert payload["source_count"]["warn"] == 29
    assert payload["actual_count"] == 1
    assert payload["new_count"] == 1
    assert payload["review_count"] == 1
    assert payload["dismiss_allowed"] is False
    assert payload["fix_allowed"] is False
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_security_findings_inventory_builds_rule_path_and_level_groups() -> None:
    payload = build_security_findings_inventory(_security(WARN_SECURITY))

    assert payload["by_rule"][0]["name"] == "SEC_HIGH_ENTROPY_STRING"
    assert payload["by_path"][0]["name"] == "src/sdetkit/adaptive_remediation_policy.py"
    assert payload["by_level"][0]["name"] == "warn"
    assert payload["items"][0]["needs_review"] is True
    assert payload["items"][0]["dismiss_allowed"] is False
    assert payload["items"][0]["fix_allowed"] is False


def test_security_findings_inventory_clean_snapshot_stays_read_only() -> None:
    payload = build_security_findings_inventory(_security(CLEAN_SECURITY))

    assert payload["status"] == "clean"
    assert payload["actual_count"] == 0
    assert payload["new_count"] == 0
    assert payload["review_count"] == 0
    assert payload["items"] == []
    assert payload["by_rule"] == []
    assert payload["dismiss_allowed"] is False
    assert payload["fix_allowed"] is False


def test_security_findings_inventory_preserves_boundary_on_nested_items() -> None:
    payload = build_security_findings_inventory(_security(WARN_SECURITY))

    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    for collection in ("items", "new_items", "by_rule", "by_path", "by_level"):
        for item in payload[collection]:
            for field, value in AUTHORITY_BOUNDARY.items():
                assert item[field] is value


def test_security_findings_inventory_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "security-findings-inventory.json"

    payload = write_security_findings_inventory_artifact(
        security_json=WARN_SECURITY,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
