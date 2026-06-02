from __future__ import annotations

import json
from pathlib import Path

from sdetkit.security_finding_disposition_matrix import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    SECURITY_ACTION_BOUNDARY,
    build_security_finding_disposition_matrix,
    write_security_finding_disposition_matrix_artifact,
)
from sdetkit.security_findings_inventory import build_security_findings_inventory

WARN_SECURITY = Path("tests/fixtures/security_followup/security-check-warn.json")
CLEAN_SECURITY = Path("tests/fixtures/security_followup/security-check-clean.json")


def _security(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory(path: Path) -> dict:
    return build_security_findings_inventory(_security(path))


def test_security_finding_disposition_matrix_classifies_warning_groups() -> None:
    payload = build_security_finding_disposition_matrix(_inventory(WARN_SECURITY))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "review required"
    assert payload["finding_count"] == 1
    assert payload["matrix_row_count"] == 1
    assert payload["disposition_counts"] == {"false positive candidate": 1}

    row = payload["matrix_rows"][0]
    assert row["rule"] == "SEC_HIGH_ENTROPY_STRING"
    assert row["level"] == "warn"
    assert row["candidate_disposition"] == "false positive candidate"
    assert row["finding_count"] == 1
    assert row["requires_human_review"] is True
    assert row["paths"][0]["path"] == "src/sdetkit/adaptive_remediation_policy.py"


def test_security_finding_disposition_matrix_keeps_actions_disabled() -> None:
    payload = build_security_finding_disposition_matrix(_inventory(WARN_SECURITY))

    assert payload["dismiss_allowed"] is False
    assert payload["suppress_allowed"] is False
    assert payload["fix_allowed"] is False
    for field, value in SECURITY_ACTION_BOUNDARY.items():
        assert payload[field] is value
    for row in payload["matrix_rows"]:
        for field, value in SECURITY_ACTION_BOUNDARY.items():
            assert row[field] is value


def test_security_finding_disposition_matrix_preserves_authority_boundary() -> None:
    payload = build_security_finding_disposition_matrix(_inventory(WARN_SECURITY))

    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    for row in payload["matrix_rows"]:
        for field, value in AUTHORITY_BOUNDARY.items():
            assert row[field] is value


def test_security_finding_disposition_matrix_clean_inventory() -> None:
    payload = build_security_finding_disposition_matrix(_inventory(CLEAN_SECURITY))

    assert payload["status"] == "clean"
    assert payload["finding_count"] == 0
    assert payload["matrix_row_count"] == 0
    assert payload["disposition_counts"] == {}
    assert payload["matrix_rows"] == []


def test_security_finding_disposition_matrix_writes_artifact(tmp_path: Path) -> None:
    inventory_path = tmp_path / "security-findings-inventory.json"
    out = tmp_path / "security-finding-disposition-matrix.json"
    inventory_path.write_text(json.dumps(_inventory(WARN_SECURITY)), encoding="utf-8")

    payload = write_security_finding_disposition_matrix_artifact(
        inventory_json=inventory_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
