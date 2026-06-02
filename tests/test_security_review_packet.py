from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit.security_finding_disposition_matrix import (
    SECURITY_ACTION_BOUNDARY,
    build_security_finding_disposition_matrix,
)
from sdetkit.security_findings_inventory import build_security_findings_inventory
from sdetkit.security_review_packet import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_security_review_packet,
    write_security_review_packet_artifact,
)

WARN_SECURITY = Path("tests/fixtures/security_followup/security-check-warn.json")
CLEAN_SECURITY = Path("tests/fixtures/security_followup/security-check-clean.json")


def _security(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory(path: Path) -> dict:
    return build_security_findings_inventory(_security(path))


def _matrix(path: Path) -> dict:
    return build_security_finding_disposition_matrix(_inventory(path))


def test_security_review_packet_combines_inventory_and_matrix_for_human_review() -> None:
    payload = build_security_review_packet(_inventory(WARN_SECURITY), _matrix(WARN_SECURITY))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "human review required"
    assert payload["decision_required"] is True
    assert payload["summary"]["source_warn_count"] == 29
    assert payload["summary"]["finding_count"] == 1
    assert payload["summary"]["matrix_row_count"] == 1
    assert payload["matrix_rows"][0]["candidate_disposition"] == "false positive candidate"
    assert payload["review_questions"]


def test_security_review_packet_keeps_all_security_actions_disabled() -> None:
    payload = build_security_review_packet(_inventory(WARN_SECURITY), _matrix(WARN_SECURITY))

    assert payload["dismiss_allowed"] is False
    assert payload["suppress_allowed"] is False
    assert payload["fix_allowed"] is False
    assert payload["issue_mutation_allowed"] is False
    for field, value in SECURITY_ACTION_BOUNDARY.items():
        assert payload[field] is value
    for section in payload["packet_sections"]:
        for field, value in SECURITY_ACTION_BOUNDARY.items():
            assert section[field] is value


def test_security_review_packet_preserves_non_authority_boundary() -> None:
    payload = build_security_review_packet(_inventory(WARN_SECURITY), _matrix(WARN_SECURITY))

    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    for section in payload["packet_sections"]:
        for field, value in AUTHORITY_BOUNDARY.items():
            assert section[field] is value


def test_security_review_packet_clean_inputs_retained_as_evidence() -> None:
    payload = build_security_review_packet(_inventory(CLEAN_SECURITY), _matrix(CLEAN_SECURITY))

    assert payload["status"] == "clean"
    assert payload["decision_required"] is False
    assert payload["summary"]["finding_count"] == 0
    assert payload["matrix_rows"] == []
    assert payload["recommended_action"] == "retain clean packet as evidence"


def test_security_review_packet_writes_artifact(tmp_path: Path) -> None:
    inventory_path = tmp_path / "security-findings-inventory.json"
    matrix_path = tmp_path / "security-finding-disposition-matrix.json"
    out = tmp_path / "security-review-packet.json"
    inventory = _inventory(WARN_SECURITY)
    matrix = build_security_finding_disposition_matrix(inventory)

    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    payload = write_security_review_packet_artifact(
        inventory_json=inventory_path,
        matrix_json=matrix_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION


def test_security_review_packet_cli_round_trip(tmp_path: Path) -> None:
    inventory_path = tmp_path / "security-findings-inventory.json"
    matrix_path = tmp_path / "security-finding-disposition-matrix.json"
    out = tmp_path / "security-review-packet.json"
    inventory = _inventory(WARN_SECURITY)
    matrix = build_security_finding_disposition_matrix(inventory)

    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security-review-packet",
            "--inventory-json",
            str(inventory_path),
            "--matrix-json",
            str(matrix_path),
            "--out",
            str(out),
            "--format",
            "text",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "review_packet_json=" in result.stdout
    assert "decision_required=true" in result.stdout
    assert "dismiss_allowed=false" in result.stdout
    assert out.is_file()
