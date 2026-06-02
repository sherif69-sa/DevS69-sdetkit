from __future__ import annotations

import json
from pathlib import Path

from sdetkit.candidate_collision_checklist import (
    AUTHORITY_BOUNDARY,
    COLLISION_CHECKS,
    SCHEMA_VERSION,
    build_candidate_collision_checklist,
    write_candidate_collision_checklist_artifact,
)
from sdetkit.candidate_evidence_checklist import build_candidate_evidence_checklist
from sdetkit.candidate_freeze_readiness import build_candidate_freeze_readiness
from sdetkit.repo_fit_screen import build_repo_fit_screen

SCREEN = Path("tests/fixtures/repo_fit/tox-screen.txt")


def _evidence_checklist() -> dict:
    repo_fit = build_repo_fit_screen(SCREEN.read_text(encoding="utf-8"))
    readiness = build_candidate_freeze_readiness(repo_fit)
    return build_candidate_evidence_checklist(readiness)


def test_candidate_collision_checklist_expands_issue_collision_review() -> None:
    payload = build_candidate_collision_checklist(_evidence_checklist())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "not ready"
    assert payload["repo"] == "tox"
    assert payload["candidate_frozen"] is False
    assert payload["freeze_ready"] is False
    assert payload["missing_issue_collision_review"] is True
    assert payload["collision_check_count"] == len(COLLISION_CHECKS)
    assert payload["missing_collision_check_count"] == len(COLLISION_CHECKS)

    names = {item["name"] for item in payload["collision_checks"]}
    assert "open issue overlap" in names
    assert "open pull request overlap" in names
    assert "first PR lane uniqueness" in names


def test_candidate_collision_checklist_items_block_freeze_and_require_human_evidence() -> None:
    payload = build_candidate_collision_checklist(_evidence_checklist())

    assert payload["collision_checks"]
    assert all(item["status"] == "missing" for item in payload["collision_checks"])
    assert all(item["blocks_freeze"] is True for item in payload["collision_checks"])
    assert all(item["required_before_freeze"] is True for item in payload["collision_checks"])
    assert all(
        item["evidence_required"] == "human-reviewed search evidence"
        for item in payload["collision_checks"]
    )
    assert all(item["query_hint"] for item in payload["collision_checks"])


def test_candidate_collision_checklist_preserves_non_authority_boundary() -> None:
    payload = build_candidate_collision_checklist(_evidence_checklist())

    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    for item in payload["collision_checks"]:
        for field, value in AUTHORITY_BOUNDARY.items():
            assert item[field] is value


def test_candidate_collision_checklist_rejects_upstream_freeze_authority() -> None:
    checklist = _evidence_checklist()
    checklist["freeze_ready"] = True
    checklist["candidate_frozen"] = True

    payload = build_candidate_collision_checklist(checklist)

    assert payload["freeze_ready"] is False
    assert payload["candidate_frozen"] is False
    assert any("cannot authorize" in block for block in payload["hard_blocks"])
    assert any("already frozen" in block for block in payload["hard_blocks"])


def test_candidate_collision_checklist_writes_artifact(tmp_path: Path) -> None:
    evidence_path = tmp_path / "candidate-evidence-checklist.json"
    out = tmp_path / "candidate-collision-checklist.json"
    evidence_path.write_text(json.dumps(_evidence_checklist()), encoding="utf-8")

    payload = write_candidate_collision_checklist_artifact(
        evidence_checklist_json=evidence_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
