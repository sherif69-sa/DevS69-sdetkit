from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit.git_inventory_collector import (
    BASE_HEAD,
    GIT_DERIVED_BASE_HEAD,
    GIT_DERIVED_STAGED_WORKTREE,
    STAGED_WORKTREE,
    collect_git_inventory,
    main,
    render_markdown,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    target = root / "src" / "sdetkit"
    target.mkdir(parents=True)
    _git(root, "init", "--quiet")
    _git(root, "config", "user.name", "Inventory Test")
    _git(root, "config", "user.email", "inventory-test@invalid.local")
    (target / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "baseline")
    return root


def test_git_inventory_collects_staged_worktree_and_untracked_paths(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    tracked = root / "src" / "sdetkit" / "example.py"
    staged = root / "src" / "sdetkit" / "staged.py"
    untracked = root / "src" / "sdetkit" / "untracked.py"

    tracked.write_text("VALUE = 2\n", encoding="utf-8")
    staged.write_text("STAGED = True\n", encoding="utf-8")
    _git(root, "add", "src/sdetkit/staged.py")
    untracked.write_text("UNTRACKED = True\n", encoding="utf-8")

    inventory = collect_git_inventory(repo_root=root, mode=STAGED_WORKTREE)

    assert inventory["status"] == "collected"
    assert inventory["mode"] == STAGED_WORKTREE
    assert inventory["changed_files_source"] == GIT_DERIVED_STAGED_WORKTREE
    assert inventory["changed_files"] == [
        "src/sdetkit/example.py",
        "src/sdetkit/staged.py",
        "src/sdetkit/untracked.py",
    ]
    assert inventory["collections"]["staged"] == ["src/sdetkit/staged.py"]
    assert inventory["collections"]["worktree"] == ["src/sdetkit/example.py"]
    assert inventory["collections"]["untracked"] == ["src/sdetkit/untracked.py"]
    assert inventory["git_inventory_verified"] is True
    assert inventory["boundary"]["shell_enabled"] is False
    assert inventory["boundary"]["automation_allowed"] is False


def test_git_inventory_collects_base_head_diff_from_resolved_commits(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base_sha = _git(root, "rev-parse", "HEAD")
    (root / "src" / "sdetkit" / "example.py").write_text("VALUE = 3\n", encoding="utf-8")
    (root / "src" / "sdetkit" / "new.py").write_text("NEW = True\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "change")

    inventory = collect_git_inventory(
        repo_root=root,
        mode=BASE_HEAD,
        base_ref=base_sha,
        head_ref="HEAD",
    )

    assert inventory["mode"] == BASE_HEAD
    assert inventory["changed_files_source"] == GIT_DERIVED_BASE_HEAD
    assert inventory["base_sha"] == base_sha
    assert inventory["head_sha"] == _git(root, "rev-parse", "HEAD")
    assert inventory["changed_files"] == [
        "src/sdetkit/example.py",
        "src/sdetkit/new.py",
    ]


def test_git_inventory_requires_base_ref_for_base_head_mode(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    with pytest.raises(ValueError, match="base_ref is required"):
        collect_git_inventory(repo_root=root, mode=BASE_HEAD)


def test_git_inventory_markdown_renders_grounded_boundary(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "src" / "sdetkit" / "example.py").write_text("VALUE = 9\n", encoding="utf-8")

    markdown = render_markdown(collect_git_inventory(repo_root=root, mode=STAGED_WORKTREE))

    assert "# Git inventory report" in markdown
    assert f"Mode: `{STAGED_WORKTREE}`" in markdown
    assert "src/sdetkit/example.py" in markdown
    assert "Read-only: `true`" in markdown
    assert "Shell enabled: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_git_inventory_cli_writes_artifacts(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    out_dir = tmp_path / "out"
    (root / "src" / "sdetkit" / "example.py").write_text("VALUE = 4\n", encoding="utf-8")

    rc = main(
        [
            "--repo-root",
            str(root),
            "--mode",
            STAGED_WORKTREE,
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "git-inventory.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "git-inventory.md").read_text(encoding="utf-8")

    assert printed["status"] == "collected"
    assert saved["changed_files"] == ["src/sdetkit/example.py"]
    assert saved["git_inventory_verified"] is True
    assert "# Git inventory report" in markdown
