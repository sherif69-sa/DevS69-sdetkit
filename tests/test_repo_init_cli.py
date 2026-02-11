from __future__ import annotations

import io
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


def test_repo_init_dry_run_plan_is_deterministic(tmp_path: Path) -> None:
    runner = CliRunner()
    args = ["repo", "init", str(tmp_path), "--allow-absolute-path", "--profile", "enterprise"]

    first = runner.invoke(args)
    second = runner.invoke(args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.stdout == second.stdout
    assert "CREATE SECURITY.md" in first.stdout
    assert "CREATE .github/workflows/security.yml" in first.stdout


def test_repo_init_apply_creates_expected_files(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "init",
            str(tmp_path),
            "--allow-absolute-path",
            "--profile",
            "enterprise",
            "--apply",
        ]
    )
    assert result.exit_code == 0

    expected = [
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/dependabot.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
    ]
    for rel in expected:
        assert (tmp_path / rel).exists()


def test_repo_init_apply_is_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    first = runner.invoke(["repo", "init", str(tmp_path), "--allow-absolute-path", "--apply"])
    second = runner.invoke(
        ["repo", "init", str(tmp_path), "--allow-absolute-path", "--apply", "--diff"]
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "repo init (apply): no changes" in second.stdout
    assert "--- a/" not in second.stdout


def test_repo_init_refuses_overwrite_without_force(tmp_path: Path) -> None:
    (tmp_path / "SECURITY.md").write_text("custom\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(["repo", "init", str(tmp_path), "--allow-absolute-path"])

    assert result.exit_code == 2
    assert "refusing to overwrite existing file: SECURITY.md" in result.stderr
    assert (tmp_path / "SECURITY.md").read_text(encoding="utf-8") == "custom\n"


def test_repo_init_force_overwrites_deterministically(tmp_path: Path) -> None:
    security = tmp_path / "SECURITY.md"
    security.write_text("custom\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "init", str(tmp_path), "--allow-absolute-path", "--apply", "--force", "--diff"]
    )

    assert result.exit_code == 0
    updated = security.read_text(encoding="utf-8")
    assert updated != "custom\n"
    assert "--- a/SECURITY.md" in result.stdout


def test_repo_init_diff_prints_unified_diff_for_changes(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(["repo", "init", str(tmp_path), "--allow-absolute-path", "--diff"])

    assert result.exit_code == 0
    assert "--- a/SECURITY.md" in result.stdout
    assert "+++ b/SECURITY.md" in result.stdout
