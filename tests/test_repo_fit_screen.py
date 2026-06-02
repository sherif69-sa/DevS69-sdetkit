from __future__ import annotations

import json
from pathlib import Path

from sdetkit.repo_fit_screen import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_repo_fit_screen,
    write_repo_fit_screen_artifact,
)

FIXTURE = Path("tests/fixtures/repo_fit/tox-screen.txt")


def _screen() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_repo_fit_screen_preserves_non_frozen_boundary() -> None:
    payload = build_repo_fit_screen(_screen())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "screen only"
    assert payload["repo"] == "tox"
    assert payload["commit"] == "28972a9932710c58f7c5b6f24d80f99aab134f00"
    assert payload["candidate_frozen"] is False
    assert payload["screen_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_repo_fit_screen_extracts_core_repo_signals() -> None:
    payload = build_repo_fit_screen(_screen())

    assert payload["signals"]["project"] is True
    assert payload["signals"]["hatch"] is True
    assert payload["signals"]["ruff"] is True
    assert payload["signals"]["pytest_ini"] is False
    assert payload["signals"]["mypy"] is False
    assert payload["counts"]["tests"] >= 80
    assert payload["counts"]["large_surface"] >= 8
    assert payload["fit"] in {"promising screen", "needs research"}


def test_repo_fit_screen_keeps_authority_false_on_samples() -> None:
    payload = build_repo_fit_screen(_screen())

    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    assert "candidate cannot be frozen" in " ".join(payload["risk_notes"])
    assert payload["recommended_action"]


def test_repo_fit_screen_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "repo-fit-screen.json"

    payload = write_repo_fit_screen_artifact(screen_text_path=FIXTURE, out=out)

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION
