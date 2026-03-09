from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert "# Contributor funnel backlog" in text
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


def test_contributor_funnel_help_describes_product_surface(capsys):
    with pytest.raises(SystemExit) as excinfo:
        contributor_funnel.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    normalized = " ".join(out.split())
    assert "usage: sdetkit contributor-funnel" in normalized
    assert "--format {text,markdown,json}" in out
    assert (
        "Generate curated good-first-issue backlog with acceptance criteria and optional issue-pack export."
        in normalized
    )
    assert "Optional file path to also write the rendered contributor funnel report." in normalized


def test_contributor_funnel_markdown_output_is_structured(capsys):
    rc = contributor_funnel.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Contributor funnel backlog" in out
    assert "| ID | Title | Area | Estimate | Acceptance criteria |" in out
    assert "## Execution notes" in out
