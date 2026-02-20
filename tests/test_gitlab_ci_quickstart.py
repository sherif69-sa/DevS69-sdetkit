import json

from sdetkit import cli, gitlab_ci_quickstart


def test_day16_quickstart_default_text(capsys):
    rc = gitlab_ci_quickstart.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 16 GitLab CI quickstart" in out


def test_day16_quickstart_json_and_strict_success(capsys):
    rc = gitlab_ci_quickstart.main(["--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "day16-gitlab-ci-quickstart"
    assert data["passed_checks"] == data["total_checks"]
    assert data["total_checks"] == 19


def test_day16_quickstart_variant_switches_pipeline(capsys):
    rc = gitlab_ci_quickstart.main(["--format", "json", "--variant", "strict", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["variant"] == "strict"
    assert "strict-gate:" in data["selected_pipeline"]


def test_day16_quickstart_strict_fails_when_content_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-gitlab-ci-quickstart.md").write_text(
        "# Placeholder\n", encoding="utf-8"
    )
    rc = gitlab_ci_quickstart.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    assert "missing checks:" in capsys.readouterr().out


def test_day16_quickstart_write_defaults_recovers_missing_file(tmp_path, capsys):
    rc = gitlab_ci_quickstart.main(
        ["--root", str(tmp_path), "--write-defaults", "--format", "json", "--strict"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["passed_checks"] == data["total_checks"]
    assert data["touched_files"] == ["docs/integrations-gitlab-ci-quickstart.md"]


def test_day16_quickstart_emit_pack(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-gitlab-ci-quickstart.md").write_text(
        gitlab_ci_quickstart._DAY16_DEFAULT_PAGE, encoding="utf-8"
    )
    rc = gitlab_ci_quickstart.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "docs/artifacts/day16-gitlab-pack",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["pack_files"]) == 6
    assert "docs/artifacts/day16-gitlab-pack/day16-sdetkit-strict.yml" in data["pack_files"]


def test_day16_quickstart_execute_writes_evidence(monkeypatch, tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-gitlab-ci-quickstart.md").write_text(
        gitlab_ci_quickstart._DAY16_DEFAULT_PAGE, encoding="utf-8"
    )

    class _Proc:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(gitlab_ci_quickstart.subprocess, "run", lambda *a, **k: _Proc())

    rc = gitlab_ci_quickstart.main(
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
    assert (tmp_path / "docs/evidence/day16-execution-summary.json").exists()


def test_day16_quickstart_execute_strict_fails_on_command_error(monkeypatch, tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-gitlab-ci-quickstart.md").write_text(
        gitlab_ci_quickstart._DAY16_DEFAULT_PAGE, encoding="utf-8"
    )

    class _Proc:
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "boom"

    monkeypatch.setattr(gitlab_ci_quickstart.subprocess, "run", lambda *a, **k: _Proc())

    rc = gitlab_ci_quickstart.main(
        ["--root", str(tmp_path), "--execute", "--format", "json", "--strict"]
    )
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["execution"]["failed_commands"] == 4


def test_main_cli_dispatches_day16_quickstart(capsys):
    rc = cli.main(["gitlab-ci-quickstart", "--format", "text"])
    assert rc == 0
    assert "Day 16 GitLab CI quickstart" in capsys.readouterr().out


def test_day16_quickstart_bootstrap_pipeline_writes_selected_variant(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/integrations-gitlab-ci-quickstart.md").write_text(
        gitlab_ci_quickstart._DAY16_DEFAULT_PAGE, encoding="utf-8"
    )

    rc = gitlab_ci_quickstart.main(
        [
            "--root",
            str(tmp_path),
            "--variant",
            "strict",
            "--bootstrap-pipeline",
            "--pipeline-path",
            ".gitlab-ci.yml",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["bootstrapped_pipeline"] == ".gitlab-ci.yml"
    assert ".gitlab-ci.yml" in data["touched_files"]
    rendered = (tmp_path / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert "strict-gate:" in rendered
