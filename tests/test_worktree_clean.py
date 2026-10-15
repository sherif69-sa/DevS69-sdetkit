"""SDETKit's own outputs and test-run caches never make a clean tree read as dirty.

Before this, a second `gate release` on a freshly committed repository refused to ship
("Commit or stash local changes") because of the files the first run left behind.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import doctor
from sdetkit.maintenance.checks import clean_tree_check
from sdetkit.maintenance.types import MaintenanceContext
from sdetkit.verdict import git_provenance
from sdetkit.worktree import uncommitted_changes

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

LEFTOVERS = (
    ".sdetkit/workspace/manifest.json",
    "build/code-scanning.sarif",
    "src/demo/__pycache__/__init__.cpython-313.pyc",
    ".pytest_cache/v/cache/nodeids",
    ".mypy_cache/3.13/demo.meta.json",
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src/demo").mkdir(parents=True)
    (tmp_path / "src/demo/__init__.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    for rel in LEFTOVERS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("{}", encoding="utf-8")
    return tmp_path


def _is_clean(root: Path) -> dict[str, bool]:
    ctx = MaintenanceContext(
        repo_root=root, python_exe=sys.executable, mode="quick", fix=False, env={}, logger=None
    )
    maintenance = clean_tree_check.run(ctx)
    return {
        "doctor": doctor._check_clean_tree(root),
        "provenance": git_provenance(root)["tree_clean"],
        "maintenance": maintenance.ok,
    }


def test_tool_outputs_leave_the_tree_clean(repo: Path) -> None:
    assert _is_clean(repo) == {"doctor": True, "provenance": True, "maintenance": True}


def test_an_untracked_source_file_still_counts(repo: Path) -> None:
    (repo / "src/demo/new.py").write_text("y = 2\n", encoding="utf-8")

    assert _is_clean(repo) == {"doctor": False, "provenance": False, "maintenance": False}


def test_a_tracked_file_counts_even_under_an_output_prefix(repo: Path) -> None:
    (repo / "build/keep.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "-f", "build/keep.txt")
    _git(repo, "commit", "-qm", "track build/keep.txt")
    (repo / "build/keep.txt").write_text("v2\n", encoding="utf-8")

    assert _is_clean(repo) == {"doctor": False, "provenance": False, "maintenance": False}


def test_uncommitted_changes_filters_only_untracked_tool_outputs() -> None:
    porcelain = "\n".join(
        [
            "?? .sdetkit/",
            "?? build/",
            "?? pkg/__pycache__/",
            "?? legacy.pyc",
            "?? newpkg/",
            " M build/tracked.json",
            " M src/app.py",
        ]
    )

    assert uncommitted_changes(porcelain) == [
        "?? newpkg/",
        " M build/tracked.json",
        " M src/app.py",
    ]
