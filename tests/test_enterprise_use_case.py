import json
import re

from sdetkit import cli, enterprise_use_case


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_enterprise_use_case_default_text(capsys):
    rc = enterprise_use_case.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Enterprise readiness report" in out
    assert "Required sections:" in out
    assert "Page:" in out


def test_enterprise_use_case_help_output_is_productized():
    out = _normalize_ws(enterprise_use_case._build_parser().format_help())
    assert "Render and validate an enterprise use-case report." in out
    assert "--format {text,markdown,json} Output format." in out
    assert "--output OUTPUT" in out
    assert "Optional file path to also write the rendered" in out


def test_enterprise_use_case_markdown_output_uses_productized_headings(capsys):
    rc = enterprise_use_case.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Enterprise readiness report" in out
    assert "## Required sections" in out
    assert "## Required commands" in out
    assert "## Use-case coverage gaps" in out
    assert "## Actions" in out
    assert "- Open page: `docs/use-cases-enterprise-regulated.md`" in out


def test_enterprise_use_case_json_and_strict_success(capsys):
    rc = enterprise_use_case.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "enterprise-readiness"
    assert data["passed_checks"] == data["total_checks"]
    assert data["total_checks"] == 15


def test_enterprise_use_case_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/use-cases-enterprise-regulated.md").write_text(
        "# Placeholder\n", encoding="utf-8"
    )
    rc = enterprise_use_case.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Use-case coverage gaps:" in out


def test_enterprise_use_case_write_defaults_recovers_missing_file(tmp_path, capsys):
    rc = enterprise_use_case.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed_checks"] == data["total_checks"]
    assert data["touched_files"] == ["docs/use-cases-enterprise-regulated.md"]
    assert (tmp_path / "docs/use-cases-enterprise-regulated.md").exists()


def test_enterprise_use_case_emit_pack(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/use-cases-enterprise-regulated.md").write_text(
        "# Enterprise + regulated workflow\n", encoding="utf-8"
    )
    rc = enterprise_use_case.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--emit-pack-dir",
            "docs/artifacts/enterprise-readiness-pack",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["pack_files"]) == 3
    assert (
        "docs/artifacts/enterprise-readiness-pack/enterprise-readiness-ci.yml" in data["pack_files"]
    )


def test_enterprise_use_case_execute_writes_evidence(monkeypatch, tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/use-cases-enterprise-regulated.md").write_text(
        enterprise_use_case._DAY13_DEFAULT_PAGE, encoding="utf-8"
    )

    class _Proc:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(enterprise_use_case.subprocess, "run", lambda *a, **k: _Proc())

    rc = enterprise_use_case.main(
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
    assert (tmp_path / "docs/evidence/day13-execution-summary.json").exists()


def test_enterprise_use_case_execute_strict_fails_on_command_error(monkeypatch, tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/use-cases-enterprise-regulated.md").write_text(
        enterprise_use_case._DAY13_DEFAULT_PAGE, encoding="utf-8"
    )

    class _Proc:
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "boom"

    monkeypatch.setattr(enterprise_use_case.subprocess, "run", lambda *a, **k: _Proc())

    rc = enterprise_use_case.main(
        ["--root", str(tmp_path), "--execute", "--format", "json", "--strict"]
    )
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["execution"]["failed_commands"] == 5


def test_main_cli_dispatches_enterprise_use_case(capsys):
    rc = cli.main(["enterprise-readiness", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Enterprise readiness report" in out
