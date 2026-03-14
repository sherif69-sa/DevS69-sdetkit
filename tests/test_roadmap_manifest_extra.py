from __future__ import annotations

import json
from pathlib import Path

from sdetkit import roadmap_manifest as rm


def test_first_heading_and_repo_root_fallback(tmp_path: Path, monkeypatch) -> None:
    assert rm._first_heading("no headings\njust text") is None
    assert rm._first_heading("intro\n## Title\n# Later") == "Title"

    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert rm._repo_root(nested) == tmp_path

    monkeypatch.chdir(nested)
    assert rm._repo_root(Path("/tmp/missing/file.py")) == nested


def test_build_manifest_merges_reports_and_plans(tmp_path: Path) -> None:
    reports = tmp_path / "docs" / "roadmap" / "reports"
    plans = tmp_path / "docs" / "roadmap" / "phase3" / "plans"
    reports.mkdir(parents=True)
    plans.mkdir(parents=True)

    (reports / "impact-3-alpha-report.md").write_text("# Day 3 report\n", encoding="utf-8")
    (reports / "impact-4-beta-report.md").write_text("text only\n", encoding="utf-8")
    (plans / "day3-plan.json").write_text('{"name": "Plan 3"}', encoding="utf-8")
    (plans / "day4-plan.json").write_text('{"title": " Plan 4 "}', encoding="utf-8")

    manifest = rm.build_manifest(repo_root=tmp_path)
    assert manifest == {
        "phases": [
            {
                "impact": 3,
                "report_path": "docs/roadmap/reports/impact-3-alpha-report.md",
                "report_title": "Day 3 report",
                "plan_path": "docs/roadmap/phase3/plans/day3-plan.json",
                "plan_title": "Plan 3",
            },
            {
                "impact": 4,
                "report_path": "docs/roadmap/reports/impact-4-beta-report.md",
                "report_title": "impact-4-beta-report.md",
                "plan_path": "docs/roadmap/phase3/plans/day4-plan.json",
                "plan_title": "Plan 4",
            },
        ]
    }


def test_build_manifest_duplicate_report_and_plan_errors(tmp_path: Path) -> None:
    reports = tmp_path / "docs" / "roadmap" / "reports"
    plans = tmp_path / "docs" / "roadmap" / "phase3" / "plans"
    reports.mkdir(parents=True)
    plans.mkdir(parents=True)

    (reports / "impact-5-a-report.md").write_text("# A\n", encoding="utf-8")
    (reports / "impact-5-b-report.md").write_text("# B\n", encoding="utf-8")

    try:
        rm.build_manifest(repo_root=tmp_path)
        raise AssertionError("expected duplicate report error")
    except ValueError as exc:
        assert "duplicate report for impact 5" in str(exc)

    # Keep one report so plan duplicate path can be reached.
    (reports / "impact-5-b-report.md").unlink()
    (plans / "day5-a.json").write_text("{}", encoding="utf-8")
    (plans / "day5-b.json").write_text("{}", encoding="utf-8")

    try:
        rm.build_manifest(repo_root=tmp_path)
        raise AssertionError("expected duplicate plan error")
    except ValueError as exc:
        assert "duplicate plan for impact 5" in str(exc)


def test_render_write_check_and_main_commands(tmp_path: Path, monkeypatch, capsys) -> None:
    docs = tmp_path / "docs" / "roadmap" / "reports"
    docs.mkdir(parents=True)
    (docs / "impact-6-gamma-report.md").write_text("# Réport\n", encoding="utf-8")

    rendered = rm.render_manifest_json(repo_root=tmp_path)
    parsed = json.loads(rendered)
    assert parsed["phases"][0]["report_title"] == "R\u00e9port"
    assert rendered.endswith("\n")

    out_path = rm.write_manifest(repo_root=tmp_path)
    assert out_path == tmp_path / "docs" / "roadmap" / "manifest.json"
    assert rm.check_manifest(repo_root=tmp_path)

    out_path.write_text("{}\n", encoding="utf-8")
    assert not rm.check_manifest(repo_root=tmp_path)

    monkeypatch.setattr(rm, "render_manifest_json", lambda repo_root=None: '{"ok": true}\n')
    assert rm.main(["print"]) == 0
    assert capsys.readouterr().out == '{"ok": true}\n'

    monkeypatch.setattr(
        rm, "write_manifest", lambda repo_root=None: Path("docs/roadmap/manifest.json")
    )
    assert rm.main(["write"]) == 0
    assert "docs/roadmap/manifest.json" in capsys.readouterr().out

    monkeypatch.setattr(rm, "check_manifest", lambda repo_root=None: True)
    assert rm.main(["check"]) == 0

    monkeypatch.setattr(rm, "check_manifest", lambda repo_root=None: False)
    assert rm.main(["check"]) == 1
    assert "roadmap manifest is stale" in capsys.readouterr().err

    assert rm.main(["--help"]) == 0
    assert "usage: python -m sdetkit.roadmap_manifest" in capsys.readouterr().out

    assert rm.main(["wat"]) == 2
    assert "unknown command" in capsys.readouterr().err
