"""Tests for executive release room audit dossier, compliance reports, and radar."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import release_room

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_release_dossier_structure() -> None:
    dossier = release_room.build_release_dossier(REPO_ROOT, title="Enterprise Release Dossier")
    assert dossier["schema_version"] == "sdetkit.release_dossier.v1"
    assert dossier["title"] == "Enterprise Release Dossier"
    assert dossier["verdict"] in ("SHIP", "REVIEW", "NO_SHIP")
    assert "readiness_score" in dossier
    assert "score_value" in dossier
    assert "compliance" in dossier
    assert dossier["compliance"]["status"] in ("CERTIFIED", "CONDITIONAL_APPROVAL")
    assert "digest" in dossier["compliance"]
    assert "dimensions" in dossier

    dims = dossier["dimensions"]
    assert "doctor" in dims
    assert "security" in dims
    assert "remediation" in dims
    assert "mutation" in dims
    assert "reliability_trend" in dims
    assert "quarantine" in dims
    assert "blast_radius" in dims
    assert "sharding" in dims
    assert "polyglot" in dims
    assert "provenance" in dims


def test_render_release_dossier_markdown() -> None:
    dossier = release_room.build_release_dossier(REPO_ROOT)
    md = release_room.render_release_dossier_markdown(dossier)
    assert "# SDETKit Executive Release Dossier" in md
    assert "Quality Radar Dimension Summary" in md
    assert "Compliance & Audit Certification" in md
    assert "Doctor Health" in md
    assert "Readiness Score:" in md


def test_render_release_dossier_html() -> None:
    dossier = release_room.build_release_dossier(REPO_ROOT)
    html = release_room.render_release_dossier_html(dossier)
    assert "<!DOCTYPE html>" in html
    assert '<html lang="en">' in html
    assert "Executive Release Dossier" in html
    assert "Quality Radar Subsystems & Compliance Matrix" in html
    assert "@media print" in html
    assert 'class="card"' in html


def test_dossier_main_formats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1. Format JSON
    json_file = tmp_path / "out.json"
    rc = release_room.dossier_main([str(REPO_ROOT), "--format", "json", "--out", str(json_file)])
    assert rc in (0, 1)
    captured = capsys.readouterr()
    assert json_file.is_file()
    payload = json.loads(json_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.release_dossier.v1"
    assert json.loads(captured.out)["schema_version"] == "sdetkit.release_dossier.v1"

    # 2. Format HTML
    html_file = tmp_path / "out.html"
    rc_html = release_room.dossier_main(
        [str(REPO_ROOT), "--format", "html", "--html-out", str(html_file)]
    )
    assert rc_html in (0, 1)
    captured_html = capsys.readouterr()
    assert "<!DOCTYPE html>" in captured_html.out
    assert html_file.is_file()
    assert "<!DOCTYPE html>" in html_file.read_text(encoding="utf-8")

    # 3. Format MD & Step Summary
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    rc_md = release_room.dossier_main([str(REPO_ROOT), "--format", "md", "--step-summary"])
    assert rc_md in (0, 1)
    captured_md = capsys.readouterr()
    assert "Executive Release Dossier" in captured_md.out
    assert summary_file.is_file()
    assert "Executive Release Dossier" in summary_file.read_text(encoding="utf-8")


def test_release_room_dispatch_plan_and_dossier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Dispatching without plan defaults to dossier_main
    rc = release_room.main(["--format", "json", str(tmp_path)])
    assert rc in (0, 1)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["schema_version"] == "sdetkit.release_dossier.v1"

    # Dispatching with plan invokes legacy _plan_main
    db_file = tmp_path / "adaptive.db"
    rc_plan = release_room.main(
        ["plan", str(tmp_path), "--db", str(db_file), "--format", "operator-json"]
    )
    assert rc_plan == 0
    captured_plan = capsys.readouterr()
    assert "signals" in captured_plan.out
