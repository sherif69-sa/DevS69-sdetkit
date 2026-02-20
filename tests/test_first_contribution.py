import json

from sdetkit import cli, first_contribution


def test_first_contribution_default_text(capsys):
    rc = first_contribution.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 10 first-contribution checklist" in out
    assert "Create and activate a virtual environment" in out
    assert "required commands:" in out


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
    assert "missing guide content:" in out


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
    assert "Day 10 first-contribution checklist" in out
