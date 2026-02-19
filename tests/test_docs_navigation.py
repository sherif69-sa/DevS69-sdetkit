import json

from sdetkit import cli, docs_navigation


def test_docs_navigation_default_text(capsys):
    rc = docs_navigation.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 11 docs navigation tune-up" in out
    assert "top journeys:" in out


def test_docs_navigation_json_and_strict_success(capsys):
    rc = docs_navigation.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "day11-docs-navigation"
    assert data["passed_checks"] == data["total_checks"]
    assert data["total_checks"] == 12
    assert any(check["id"] == "day11-top-journeys-header" for check in data["checks"])


def test_docs_navigation_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/index.md").write_text("# Docs\n", encoding="utf-8")
    rc = docs_navigation.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "missing docs navigation content:" in out


def test_docs_navigation_write_defaults_recovers_missing_quick_jump(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/index.md").write_text(
        "## Day 11 ultra upgrades (docs navigation tune-up)\n\n<div class=\"quick-jump\" markdown>\nold\n</div>\n",
        encoding="utf-8",
    )
    rc = docs_navigation.main(["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["touched_files"] == ["docs/index.md"]
    assert data["passed_checks"] == data["total_checks"]
    repaired = (tmp_path / "docs/index.md").read_text(encoding="utf-8")
    assert "[🧭 Day 11 ultra report](day-11-ultra-upgrade-report.md)" in repaired
    assert "### Day 11 top journeys" in repaired


def test_docs_navigation_write_defaults_bootstraps_missing_docs_index(tmp_path, capsys):
    rc = docs_navigation.main(["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["touched_files"] == ["docs/index.md"]
    assert data["passed_checks"] == data["total_checks"]
    assert (tmp_path / "docs/index.md").exists()


def test_main_cli_dispatches_docs_navigation(capsys):
    rc = cli.main(["docs-nav", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 11 docs navigation tune-up" in out
