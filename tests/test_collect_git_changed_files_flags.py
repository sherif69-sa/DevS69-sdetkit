from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sdetkit.repo import collect_git_changed_files


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_collect_git_changed_files_respects_staged_and_untracked_flags(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")

    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    (repo / "tracked.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "c1")

    (repo / "tracked.txt").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "c2")

    (repo / "staged.txt").write_text("stage\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")

    (repo / "untracked.txt").write_text("u\n", encoding="utf-8")

    all_changed = collect_git_changed_files(
        repo,
        since_ref="HEAD~1",
        include_untracked=True,
        include_staged=True,
    )
    assert "tracked.txt" in all_changed
    assert "staged.txt" in all_changed
    assert "untracked.txt" in all_changed

    no_untracked = collect_git_changed_files(
        repo,
        since_ref="HEAD~1",
        include_untracked=False,
        include_staged=True,
    )
    assert "tracked.txt" in no_untracked
    assert "staged.txt" in no_untracked
    assert "untracked.txt" not in no_untracked

    no_staged = collect_git_changed_files(
        repo,
        since_ref="HEAD~1",
        include_untracked=True,
        include_staged=False,
    )
    assert "tracked.txt" in no_staged
    assert "staged.txt" not in no_staged
    assert "untracked.txt" in no_staged

    neither = collect_git_changed_files(
        repo,
        since_ref="HEAD~1",
        include_untracked=False,
        include_staged=False,
    )
    assert "tracked.txt" in neither
    assert "staged.txt" not in neither
    assert "untracked.txt" not in neither
