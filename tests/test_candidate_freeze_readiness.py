from __future__ import annotations

import json
from pathlib import Path

from sdetkit.candidate_freeze_readiness import (
    AUTHORITY_BOUNDARY,
    REQUIRED_EVIDENCE,
    SCHEMA_VERSION,
    build_candidate_freeze_readiness,
    write_candidate_freeze_readiness_artifact,
)
from sdetkit.repo_fit_screen import build_repo_fit_screen, write_repo_fit_screen_artifact

SCREEN = Path("tests/fixtures/repo_fit/tox-screen.txt")


def _repo_fit() -> dict:
    return build_repo_fit_screen(SCREEN.read_text(encoding="utf-8"))


def test_candidate_freeze_readiness_keeps_promising_screen_unfrozen() -> None:
    payload = build_candidate_freeze_readiness(_repo_fit())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["repo"] == "tox"
    assert payload["status"] == "not ready"
    assert payload["screen_valid"] is True
    assert payload["promising_screen"] is True
    assert payload["candidate_frozen"] is False
    assert payload["freeze_ready"] is False
    assert payload["readiness_score"] > 0
    assert payload["missing_evidence"] == REQUIRED_EVIDENCE


def test_candidate_freeze_readiness_emits_review_first_authority_boundary() -> None:
    payload = build_candidate_freeze_readiness(_repo_fit())

    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value


def test_candidate_freeze_readiness_blocks_non_screen_or_weak_fit() -> None:
    repo_fit = _repo_fit()
    repo_fit["screen_only"] = False
    repo_fit["fit"] = "weak screen"

    payload = build_candidate_freeze_readiness(repo_fit)

    assert payload["screen_valid"] is False
    assert payload["promising_screen"] is False
    assert payload["freeze_ready"] is False
    assert len(payload["hard_blocks"]) == 2


def test_candidate_freeze_readiness_writes_artifact(tmp_path: Path) -> None:
    repo_fit_path = tmp_path / "repo-fit-screen.json"
    out = tmp_path / "candidate-freeze-readiness.json"
    write_repo_fit_screen_artifact(screen_text_path=SCREEN, out=repo_fit_path)

    payload = write_candidate_freeze_readiness_artifact(
        repo_fit_json=repo_fit_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
