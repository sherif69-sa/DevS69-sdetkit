from __future__ import annotations

import json
from pathlib import Path

from sdetkit import contributor_funnel


def test_day8_backlog_has_ten_curated_issues() -> None:
    payload = json.loads(contributor_funnel._render_json(contributor_funnel.build_backlog()))
    assert payload["name"] == "day8-contributor-funnel"
    assert payload["kpis"]["issue_count"] == 10
    assert len(payload["issues"]) == 10
    assert all(len(item["acceptance"]) >= 3 for item in payload["issues"])


def test_markdown_output_and_issue_pack_written(tmp_path: Path) -> None:
    out = tmp_path / "day8.md"
    pack_dir = tmp_path / "issue-pack"
    rc = contributor_funnel.main(
        [
            "--format",
            "markdown",
            "--output",
            str(out),
            "--issue-pack-dir",
            str(pack_dir),
        ]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "# Day 8 contributor funnel backlog" in text
    assert "`GFI-10`" in text
    files = sorted(p.name for p in pack_dir.glob("*.md"))
    assert files[0] == "gfi-01.md"
    assert files[-1] == "gfi-10.md"
    assert len(files) == 10


def test_area_filter_returns_subset() -> None:
    docs_only = contributor_funnel.build_backlog("docs")
    tests_only = contributor_funnel.build_backlog("tests")
    assert docs_only
    assert tests_only
    assert all(item["area"] == "docs" for item in docs_only)
    assert all(item["area"] == "tests" for item in tests_only)
