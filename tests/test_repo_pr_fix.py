from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sdetkit import cli, repo


class Result:
    def __init__(self, exit_code: int, stdout: str, stderr: str) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class CliRunner:
    def invoke(self, args: list[str]) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(args)
        return Result(code, stdout.getvalue(), stderr.getvalue())


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    (root / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)


def test_pr_fix_apply_commit_creates_branch_and_commit(tmp_path: Path, monkeypatch) -> None:
    _init_git_repo(tmp_path)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "pr-fix",
            str(tmp_path),
            "--allow-absolute-path",
            "--apply",
            "--force-branch",
            "--branch",
            "sdetkit/fix-audit",
        ]
    )
    assert result.exit_code == 0
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == "sdetkit/fix-audit"
    commit_time = subprocess.run(
        ["git", "show", "--format=%ct", "--no-patch"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    assert commit_time == "1700000000"


def test_pr_fix_no_changes_exits_zero_without_commit(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runner = CliRunner()
    prepared = runner.invoke(
        ["repo", "fix-audit", str(tmp_path), "--allow-absolute-path", "--apply", "--force"]
    )
    assert prepared.exit_code == 0
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "prepared"], cwd=tmp_path, check=True, capture_output=True
    )
    result = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--allow-absolute-path", "--apply", "--force-branch"]
    )
    assert result.exit_code == 0
    assert "no changes" in result.stdout


def test_pr_fix_open_pr_requires_token(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "pr-fix",
            str(tmp_path),
            "--allow-absolute-path",
            "--apply",
            "--open-pr",
            "--force-branch",
        ]
    )
    assert result.exit_code == 2
    assert "missing GitHub token" in result.stderr


def test_pr_body_deterministic_ordering() -> None:
    body = repo._build_pr_body(
        profile="default",
        packs=["enterprise", "core"],
        rule_ids=["B", "A"],
        changed_files=["b.txt", "a.txt"],
        per_project=[],
    )
    assert "`A, B`" in body
    assert body.index("`a.txt`") < body.index("`b.txt`")


def test_pr_fix_no_network_calls_without_open_pr(tmp_path: Path, monkeypatch) -> None:
    _init_git_repo(tmp_path)
    called = {"count": 0}

    def _blocked(*_args, **_kwargs):
        called["count"] += 1
        raise AssertionError("network should not be called")

    monkeypatch.setattr(repo.urllib.request, "urlopen", _blocked)
    runner = CliRunner()
    result = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--allow-absolute-path", "--apply", "--force-branch"]
    )
    assert result.exit_code == 0
    assert called["count"] == 0
