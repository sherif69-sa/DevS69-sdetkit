import json
import re

from sdetkit import cli, first_contribution


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_first_contribution_default_text(capsys):
    rc = first_contribution.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "First contribution checklist report" in out
    assert "Create and activate a virtual environment" in out
    assert "Required commands:" in out
    assert "Guide file:" in out


def test_first_contribution_help_output_is_productized():
    out = _normalize_ws(first_contribution._build_parser().format_help())
    assert "Render and validate a first-contribution checklist report." in out
    assert "--format {text,markdown,json} Output format." in out
    assert "--output OUTPUT" in out
    assert "Optional file path to also write the rendered" in out


def test_first_contribution_markdown_output_uses_productized_headings(capsys):
    rc = first_contribution.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# First contribution checklist report" in out
    assert "## Checklist" in out
    assert "## Required command sequence" in out
    assert "## Guide coverage gaps" in out
    assert "## Actions" in out
    assert "- Open guide: `docs/contributing.md`" in out


def test_first_contribution_json_and_strict_success(capsys):
    rc = first_contribution.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "day10-first-contribution-checklist"
    assert data["passed_checks"] == data["total_checks"]
    assert "mkdocs build" in data["required_commands"]


def test_first_contribution_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
    rc = first_contribution.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Guide coverage gaps:" in out


def test_first_contribution_write_defaults_recovers_missing_file(tmp_path, capsys):
    rc = first_contribution.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed_checks"] == data["total_checks"]
    assert data["touched_files"] == ["CONTRIBUTING.md"]
    assert (tmp_path / "CONTRIBUTING.md").exists()


def test_main_cli_dispatches_first_contribution(capsys):
    rc = cli.main(["first-contribution", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "First contribution checklist report" in out
