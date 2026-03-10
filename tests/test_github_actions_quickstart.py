import json
import re

from sdetkit import cli, github_actions_quickstart


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_day15_quickstart_default_text(capsys):
    rc = github_actions_quickstart.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "GitHub Actions quickstart report" in out
    assert "Required sections:" in out
    assert "Page:" in out


def test_day15_quickstart_help_output_is_productized():
    out = _normalize_ws(github_actions_quickstart._build_parser().format_help())
    assert "Render and validate a GitHub Actions quickstart report." in out
    assert "--format {text,markdown,json} Output format." in out
    assert "--output OUTPUT" in out
    assert "Optional file path to also write the rendered" in out
    assert "GitHub Actions quickstart report." in out


def test_day15_quickstart_markdown_output_uses_productized_headings(capsys):
    rc = github_actions_quickstart.main(["--format", "markdown", "--variant", "strict"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# GitHub Actions quickstart report" in out
    assert "## Required sections" in out
    assert "## Required commands" in out
    assert "## Selected workflow" in out
    assert "## Quickstart coverage gaps" in out
    assert "## Actions" in out
    assert "name: sdetkit-github-strict" in out
    assert "- Open page: `docs/integrations-github-actions-quickstart.md`" in out


def test_day15_quickstart_json_and_strict_success(capsys):
    rc = github_actions_quickstart.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "day15-github-actions-quickstart"
    assert data["passed_checks"] == data["total_checks"]
    assert data["total_checks"] == 18


def test_day15_quickstart_variant_switches_workflow(capsys):
    rc = github_actions_quickstart.main(["--format", "json", "--variant", "strict", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["variant"] == "strict"
    assert "name: sdetkit-github-strict" in data["selected_workflow"]


def test_day15_quickstart_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-github-actions-quickstart.md").write_text(
        "# Placeholder\n", encoding="utf-8"
    )
    rc = github_actions_quickstart.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Quickstart coverage gaps:" in out


def test_day15_quickstart_write_defaults_recovers_missing_file(tmp_path, capsys):
    rc = github_actions_quickstart.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed_checks"] == data["total_checks"]
    assert data["touched_files"] == ["docs/integrations-github-actions-quickstart.md"]


def test_day15_quickstart_emit_pack(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-github-actions-quickstart.md").write_text(
        github_actions_quickstart._DAY15_DEFAULT_PAGE, encoding="utf-8"
    )
    rc = github_actions_quickstart.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "docs/artifacts/day15-github-pack",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["pack_files"]) == 6
    assert "docs/artifacts/day15-github-pack/day15-sdetkit-strict.yml" in data["pack_files"]


def test_day15_quickstart_execute_writes_evidence(monkeypatch, tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-github-actions-quickstart.md").write_text(
        github_actions_quickstart._DAY15_DEFAULT_PAGE, encoding="utf-8"
    )

    class _Proc:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(github_actions_quickstart.subprocess, "run", lambda *a, **k: _Proc())

    rc = github_actions_quickstart.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "docs/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["execution"]["failed_commands"] == 0
    assert (tmp_path / "docs/evidence/day15-execution-summary.json").exists()


def test_day15_quickstart_execute_strict_fails_on_command_error(monkeypatch, tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-github-actions-quickstart.md").write_text(
        github_actions_quickstart._DAY15_DEFAULT_PAGE, encoding="utf-8"
    )

    class _Proc:
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "boom"

    monkeypatch.setattr(github_actions_quickstart.subprocess, "run", lambda *a, **k: _Proc())

    rc = github_actions_quickstart.main(
        ["--root", str(tmp_path), "--execute", "--format", "json", "--strict"]
    )
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["execution"]["failed_commands"] == 4


def test_main_cli_dispatches_day15_quickstart(capsys):
    rc = cli.main(["github-actions-quickstart", "--format", "text"])
    assert rc == 0
    assert "GitHub Actions quickstart report" in capsys.readouterr().out
