import json
import re

from sdetkit import cli, startup_use_case


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_startup_use_case_default_text(capsys):
    rc = startup_use_case.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Startup readiness report" in out
    assert "Required sections:" in out
    assert "Page:" in out


def test_startup_use_case_help_output_is_productized():
    out = _normalize_ws(startup_use_case._build_parser().format_help())
    assert "Render and validate a startup use-case report." in out
    assert "--format {text,markdown,json} Output format." in out
    assert "--output OUTPUT" in out
    assert "Optional file path to also write the rendered" in out


def test_startup_use_case_markdown_output_uses_productized_headings(capsys):
    rc = startup_use_case.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Startup readiness report" in out
    assert "## Required sections" in out
    assert "## Required commands" in out
    assert "## Use-case coverage gaps" in out
    assert "## Actions" in out
    assert "- Open page: `docs/use-cases-startup-small-team.md`" in out


def test_startup_use_case_json_and_strict_success(capsys):
    rc = startup_use_case.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "day12-startup-readiness"
    assert data["passed_checks"] == data["total_checks"]
    assert data["total_checks"] == 14


def test_startup_use_case_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/use-cases-startup-small-team.md").write_text(
        "# Placeholder\n", encoding="utf-8"
    )
    rc = startup_use_case.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Use-case coverage gaps:" in out


def test_startup_use_case_write_defaults_recovers_missing_file(tmp_path, capsys):
    rc = startup_use_case.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed_checks"] == data["total_checks"]
    assert data["touched_files"] == ["docs/use-cases-startup-small-team.md"]
    assert (tmp_path / "docs/use-cases-startup-small-team.md").exists()


def test_startup_use_case_emit_pack(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/use-cases-startup-small-team.md").write_text(
        "# Startup + small-team workflow\n", encoding="utf-8"
    )
    rc = startup_use_case.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--emit-pack-dir",
            "docs/artifacts/day12-startup-pack",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["pack_files"]) == 3
    assert "docs/artifacts/day12-startup-pack/startup-day12-ci.yml" in data["pack_files"]


def test_main_cli_dispatches_startup_use_case(capsys):
    rc = cli.main(["startup-readiness", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Startup readiness report" in out
