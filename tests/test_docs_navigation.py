import json
import re

from sdetkit import cli, docs_navigation


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_docs_navigation_default_text(capsys):
    rc = docs_navigation.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Docs navigation report" in out
    assert "Top journeys:" in out
    assert "Docs home:" in out


def test_docs_navigation_help_output_is_productized():
    out = _normalize_ws(docs_navigation._build_parser().format_help())
    assert "Render and validate a docs governance report." in out
    assert "--format {text,markdown,json} Output format." in out
    assert "--output OUTPUT" in out
    assert "Optional file path to also write the rendered" in out


def test_docs_navigation_markdown_output_uses_productized_headings(capsys):
    rc = docs_navigation.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Docs navigation report" in out
    assert "## Top journeys" in out
    assert "## Required one-click links" in out
    assert "## Docs coverage gaps" in out
    assert "## Actions" in out
    assert "- Open docs home: `docs/index.md`" in out


def test_docs_navigation_json_and_strict_success(capsys):
    rc = docs_navigation.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "docs-governance"
    assert data["passed_checks"] == data["total_checks"]
    assert data["total_checks"] == 12
    assert any(check["id"] == "legacy-reports-section" for check in data["checks"])


def test_docs_navigation_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/index.md").write_text("# Docs\n", encoding="utf-8")
    rc = docs_navigation.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Docs coverage gaps:" in out


def test_docs_navigation_write_defaults_recovers_missing_quick_jump(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/index.md").write_text(
        '## Legacy reports\n\n<div class="quick-jump" markdown>\nold\n</div>\n',
        encoding="utf-8",
    )
    rc = docs_navigation.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["touched_files"] == ["docs/index.md"]
    assert data["passed_checks"] == data["total_checks"]
    repaired = (tmp_path / "docs/index.md").read_text(encoding="utf-8")
    assert "[🧭 Repo tour](repo-tour.md)" in repaired
    assert "### Top journeys" in repaired


def test_docs_navigation_write_defaults_bootstraps_missing_docs_index(tmp_path, capsys):
    rc = docs_navigation.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["touched_files"] == ["docs/index.md"]
    assert data["passed_checks"] == data["total_checks"]
    assert (tmp_path / "docs/index.md").exists()


def test_main_cli_dispatches_docs_navigation(capsys):
    rc = cli.main(["docs-governance", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Docs navigation report" in out


def test_docs_navigation_extract_quick_jump_missing_end_returns_empty():
    text = f"hello {docs_navigation._QUICK_JUMP_START} still-open"
    assert docs_navigation._extract_quick_jump(text) == ""


def test_docs_navigation_write_defaults_noop_when_already_clean(tmp_path):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/index.md").write_text("# Documentation Home\n", encoding="utf-8")

    first = docs_navigation._write_defaults(tmp_path)
    assert first == ["docs/index.md"]

    second = docs_navigation._write_defaults(tmp_path)
    assert second == []


def test_docs_navigation_write_defaults_repairs_existing_top_journeys_without_duplication(tmp_path):
    (tmp_path / "docs").mkdir(parents=True)
    content = (
        "# Documentation Home\n\n"
        + docs_navigation._DEFAULT_QUICK_JUMP_BLOCK
        + "\n\n"
        + docs_navigation._LEGACY_REPORTS_SECTION_HEADER
        + "\n\n"
        + "### Top journeys\n\n"
        + "- Run first command in under 60 seconds\n"
        + "\n## Next section\n"
    )
    (tmp_path / "docs/index.md").write_text(content, encoding="utf-8")

    touched = docs_navigation._write_defaults(tmp_path)
    assert touched == ["docs/index.md"]

    repaired = (tmp_path / "docs/index.md").read_text(encoding="utf-8")
    assert repaired.count("### Top journeys") == 1
    for journey in docs_navigation._TOP_JOURNEYS:
        assert f"- {journey}" in repaired


def test_docs_navigation_markdown_output_file_written(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    content = (
        "# Documentation Home\n\n"
        + docs_navigation._DEFAULT_QUICK_JUMP_BLOCK
        + "\n\n"
        + docs_navigation._LEGACY_REPORTS_SECTION_HEADER
        + "\n\n"
        + docs_navigation._DEFAULT_JOURNEYS_BLOCK
        + "\n"
    )
    (tmp_path / "docs/index.md").write_text(content, encoding="utf-8")

    out_path = tmp_path / "out.md"
    rc = docs_navigation.main(
        ["--root", str(tmp_path), "--format", "markdown", "--output", str(out_path), "--strict"]
    )
    assert rc == 0

    written = out_path.read_text(encoding="utf-8")
    assert "# Docs navigation report" in written
    assert "## Docs coverage gaps" in written
    assert "- none" in written
