from __future__ import annotations

import json
from pathlib import Path

from sdetkit import roadmap


def test_load_manifest_resolves_report_and_plan_paths(tmp_path: Path, monkeypatch) -> None:
    manifest_dir = tmp_path / "docs" / "roadmap"
    manifest_dir.mkdir(parents=True)

    report = tmp_path / "docs" / "roadmap" / "reports" / "day01-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("report", encoding="utf-8")

    plan = tmp_path / "docs" / "roadmap" / "phase3" / "plans" / "day01-plan.json"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("{}", encoding="utf-8")

    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {"phases": [{"day": 1, "report_file": "day01-report.md", "plan_file": "day01-plan.json"}]}
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(roadmap, "_repo_root", lambda: tmp_path)
    entries = roadmap.load_manifest()

    assert len(entries) == 1
    assert entries[0].report_path == "docs/roadmap/reports/day01-report.md"
    assert entries[0].plan_path == "docs/roadmap/phase3/plans/day01-plan.json"


def test_load_manifest_handles_dot_prefixed_plan_candidates(tmp_path: Path, monkeypatch) -> None:
    manifest_dir = tmp_path / "docs" / "roadmap"
    manifest_dir.mkdir(parents=True)

    dot_plan = tmp_path / ".day02-plan.json"
    dot_plan.write_text("{}", encoding="utf-8")
    (manifest_dir / "manifest.json").write_text(
        json.dumps({"phases": [{"day": 2, "report_file": None, "plan_file": ".day02-plan.json"}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(roadmap, "_repo_root", lambda: tmp_path)
    entries = roadmap.load_manifest()

    assert len(entries) == 1
    assert entries[0].report_path is None
    assert entries[0].plan_path == ".day02-plan.json"


def test_roadmap_main_show_open_and_error_paths(monkeypatch, capsys, tmp_path: Path) -> None:
    entry = roadmap.RoadmapEntry(
        day=9,
        report_file="day09-report.md",
        plan_file="day09-plan.json",
        report_path="docs/day09-report.md",
        plan_path="docs/day09-plan.json",
    )
    monkeypatch.setattr(roadmap, "load_manifest", lambda: [entry])
    monkeypatch.setattr(roadmap, "_repo_root", lambda: tmp_path)

    assert roadmap.main(["show", "9"]) == 0
    show_payload = json.loads(capsys.readouterr().out)
    assert show_payload["day"] == 9

    assert roadmap.main(["open", "9", "plan"]) == 0
    open_out = capsys.readouterr().out.strip()
    assert open_out.endswith("/docs/day09-plan.json")

    assert roadmap.main(["open", "9", "report"]) == 0
    assert capsys.readouterr().out.strip().endswith("/docs/day09-report.md")

    assert roadmap.main(["show", "not-a-day"]) == 2
    assert capsys.readouterr().err.strip() == "roadmap: invalid day"

    assert roadmap.main(["show", "99"]) == 2
    assert capsys.readouterr().err.strip() == "roadmap: unknown day"


def test_roadmap_open_file_not_found_for_selected_kind(monkeypatch, capsys) -> None:
    entry = roadmap.RoadmapEntry(
        day=10,
        report_file="day10-report.md",
        plan_file="day10-plan.json",
        report_path="docs/day10-report.md",
        plan_path=None,
    )
    monkeypatch.setattr(roadmap, "load_manifest", lambda: [entry])

    assert roadmap.main(["open", "10", "plan"]) == 2
    assert capsys.readouterr().err.strip() == "roadmap: file not found"


def test_roadmap_main_list_help_and_unknown_command(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        roadmap,
        "load_manifest",
        lambda: [
            roadmap.RoadmapEntry(1, None, None, None, None),
            roadmap.RoadmapEntry(2, "r.md", "p.json", "docs/r.md", "docs/p.json"),
        ],
    )

    assert roadmap.main([]) == 0
    assert "usage: sdetkit roadmap" in capsys.readouterr().out

    assert roadmap.main(["list"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["01 - -", "02 R P"]

    assert roadmap.main(["open"]) == 2
    assert capsys.readouterr().err.strip() == "roadmap: missing day"

    assert roadmap.main(["wat"]) == 2
    assert capsys.readouterr().err.strip() == "roadmap: unknown command"
