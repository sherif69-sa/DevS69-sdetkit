from __future__ import annotations

import json
from pathlib import Path

from sdetkit.candidate_evidence_checklist import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_candidate_evidence_checklist,
    write_candidate_evidence_checklist_artifact,
)
from sdetkit.candidate_freeze_readiness import build_candidate_freeze_readiness
from sdetkit.repo_fit_screen import build_repo_fit_screen, write_repo_fit_screen_artifact

SCREEN = Path("tests/fixtures/repo_fit/tox-screen.txt")


def _readiness() -> dict:
    repo_fit = build_repo_fit_screen(SCREEN.read_text(encoding="utf-8"))
    return build_candidate_freeze_readiness(repo_fit)


def test_candidate_evidence_checklist_expands_missing_readiness_evidence() -> None:
    payload = build_candidate_evidence_checklist(_readiness())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "not ready"
    assert payload["repo"] == "tox"
    assert payload["candidate_frozen"] is False
    assert payload["freeze_ready"] is False
    assert payload["required_item_count"] == 6
    assert payload["missing_item_count"] == 6
    assert payload["present_item_count"] == 0

    names = {item["name"] for item in payload["checklist_items"]}
    assert "issue collision review" in names
    assert "local proof feasibility" in names
    assert "candidate owner approval" in names


def test_candidate_evidence_checklist_items_are_review_first_and_block_freeze() -> None:
    payload = build_candidate_evidence_checklist(_readiness())

    assert payload["checklist_items"]
    assert all(item["required_before_freeze"] is True for item in payload["checklist_items"])
    assert all(item["blocks_freeze"] is True for item in payload["checklist_items"])
    assert all(item["status"] == "missing" for item in payload["checklist_items"])
    assert all(item["suggested_proof"] for item in payload["checklist_items"])

    for item in payload["checklist_items"]:
        for field, value in AUTHORITY_BOUNDARY.items():
            assert item[field] is value


def test_candidate_evidence_checklist_preserves_non_authority_boundary() -> None:
    payload = build_candidate_evidence_checklist(_readiness())

    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value


def test_candidate_evidence_checklist_does_not_trust_upstream_freeze_ready() -> None:
    readiness = _readiness()
    readiness["freeze_ready"] = True
    readiness["candidate_frozen"] = True
    readiness["missing_evidence"] = []

    payload = build_candidate_evidence_checklist(readiness)

    assert payload["status"] == "ready for human freeze review"
    assert payload["freeze_ready"] is False
    assert payload["candidate_frozen"] is False
    assert any("cannot authorize" in block for block in payload["hard_blocks"])
    assert any("frozen before checklist review" in block for block in payload["hard_blocks"])


def test_candidate_evidence_checklist_writes_artifact(tmp_path: Path) -> None:
    repo_fit_path = tmp_path / "repo-fit-screen.json"
    readiness_path = tmp_path / "candidate-freeze-readiness.json"
    out = tmp_path / "candidate-evidence-checklist.json"

    write_repo_fit_screen_artifact(screen_text_path=SCREEN, out=repo_fit_path)
    readiness = build_candidate_freeze_readiness(
        json.loads(repo_fit_path.read_text(encoding="utf-8"))
    )
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    payload = write_candidate_evidence_checklist_artifact(
        readiness_json=readiness_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
