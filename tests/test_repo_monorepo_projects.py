from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

from sdetkit import cli


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str


class CliRunner:
    def invoke(self, args: list[str]) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli.main(args)
        return Result(exit_code=exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def _seed_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / "CONTRIBUTING.md").write_text("guide\n", encoding="utf-8")
    (root / "CODE_OF_CONDUCT.md").write_text("code\n", encoding="utf-8")
    (root / "SECURITY.md").write_text("security\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("changes\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "noxfile.py").write_text("\n", encoding="utf-8")
    (root / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "requirements-test.txt").write_text("pytest\n", encoding="utf-8")
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (wf / "security.yml").write_text("name: security\n", encoding="utf-8")


def _seed_monorepo(root: Path) -> None:
    _seed_project(root / "services" / "api")
    _seed_project(root / "libs" / "core")
    (root / ".sdetkit").mkdir(parents=True)
    (root / ".sdetkit" / "projects.toml").write_text(
        """
[[project]]
name = "api"
root = "services/api"
exclude = ["docs/*"]

[[project]]
name = "core"
root = "libs/core"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_projects_list_json_is_deterministic(tmp_path: Path) -> None:
    _seed_monorepo(tmp_path)
    runner = CliRunner()
    first = runner.invoke(
        ["repo", "projects", "list", str(tmp_path), "--allow-absolute-path", "--json"]
    )
    second = runner.invoke(
        ["repo", "projects", "list", str(tmp_path), "--allow-absolute-path", "--json"]
    )
    assert first.exit_code == 0
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert [item["name"] for item in payload["projects"]] == ["api", "core"]


def test_audit_all_projects_json_and_sarif_runs(tmp_path: Path) -> None:
    _seed_monorepo(tmp_path)
    (tmp_path / "services" / "api" / "CONTRIBUTING.md").unlink()

    runner = CliRunner()
    out_json = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--all-projects",
            "--format",
            "json",
        ]
    )
    assert out_json.exit_code == 1
    payload = json.loads(out_json.stdout)
    assert payload["schema_version"] == "sdetkit.audit.aggregate.v1"
    assert len(payload["projects"]) == 2

    out_sarif = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--all-projects",
            "--format",
            "sarif",
        ]
    )
    sarif = json.loads(out_sarif.stdout)
    assert len(sarif["runs"]) == 2


def test_fix_audit_project_scoped_only(tmp_path: Path) -> None:
    _seed_monorepo(tmp_path)
    (tmp_path / "services" / "api" / "SECURITY.md").unlink()
    (tmp_path / "libs" / "core" / "SECURITY.md").unlink()

    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--project",
            "api",
            "--apply",
            "--force",
        ]
    )
    assert result.exit_code == 0
    assert (tmp_path / "services" / "api" / "SECURITY.md").exists()
    assert not (tmp_path / "libs" / "core" / "SECURITY.md").exists()


def test_all_projects_audit_idempotent_json(tmp_path: Path) -> None:
    _seed_monorepo(tmp_path)
    runner = CliRunner()
    first = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--all-projects",
            "--format",
            "json",
        ]
    )
    second = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--all-projects",
            "--format",
            "json",
        ]
    )
    assert first.stdout == second.stdout
