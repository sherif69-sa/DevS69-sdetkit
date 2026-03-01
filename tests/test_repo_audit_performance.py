from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from sdetkit import cli


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True, capture_output=True
    )
    return proc.stdout.strip()


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / "SECURITY.md").write_text("ok\n", encoding="utf-8")
    (root / "CODE_OF_CONDUCT.md").write_text("ok\n", encoding="utf-8")
    (root / "CONTRIBUTING.md").write_text("ok\n", encoding="utf-8")
    (root / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    (root / ".github" / "ISSUE_TEMPLATE" / "config.yml").write_text(
        "blank_issues_enabled: false\n", encoding="utf-8"
    )
    _git(root, "init")
    _git(root, "config", "user.email", "dev@example.com")
    _git(root, "config", "user.name", "dev")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")


def _run_capture(root: Path, *extra: str) -> tuple[int, dict]:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out = Path(f.name)
    try:
        rc = cli.main(
            [
                "repo",
                "audit",
                str(root),
                "--allow-absolute-path",
                "--format",
                "json",
                "--output",
                str(out),
                "--force",
                *extra,
            ]
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
    finally:
        try:
            out.unlink()
        except FileNotFoundError:
            pass
    return rc, payload


def test_changed_only_collects_git_states(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "CONTRIBUTING.md").write_text("changed\n", encoding="utf-8")  # unstaged
    (tmp_path / "SECURITY.md").write_text("changed\n", encoding="utf-8")
    _git(tmp_path, "add", "SECURITY.md")  # staged
    (tmp_path / "new.txt").write_text("new\n", encoding="utf-8")  # untracked

    rc, payload = _run_capture(tmp_path, "--changed-only", "--cache-stats")
    assert rc in {0, 1}
    assert payload["summary"]["incremental"]["used"] is True
    assert payload["summary"]["incremental"]["changed_files"] >= 3


def test_cache_hit_and_invalidation(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    first_rc, first = _run_capture(tmp_path, "--cache-stats")
    second_rc, second = _run_capture(tmp_path, "--cache-stats")
    assert first_rc in {0, 1} and second_rc in {0, 1}
    assert second["summary"]["cache"]["hits"]

    (tmp_path / "SECURITY.md").write_text("changed\n", encoding="utf-8")
    third_rc, third = _run_capture(tmp_path, "--cache-stats")
    assert third_rc in {0, 1}
    assert third["summary"]["cache"]["misses"]


def test_no_cache_disables_stats_and_parallel_order_stable(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc1, serial = _run_capture(tmp_path, "--jobs", "1", "--no-cache")
    rc2, parallel = _run_capture(tmp_path, "--jobs", "4", "--no-cache")
    assert rc1 in {0, 1} and rc2 in {0, 1}
    assert serial["findings"] == parallel["findings"]


def test_non_git_fallback_and_require_git(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    rc = cli.main(["repo", "audit", str(tmp_path), "--allow-absolute-path", "--changed-only"])
    assert rc in {0, 1}
    rc2 = cli.main(
        ["repo", "audit", str(tmp_path), "--allow-absolute-path", "--changed-only", "--require-git"]
    )
    assert rc2 == 2


def test_cache_hit_survives_unrelated_file_change(tmp_path: Path) -> None:
    _seed_repo(tmp_path)

    first_rc, first = _run_capture(tmp_path, "--cache-stats")
    assert first_rc in {0, 1}
    assert first["summary"]["cache"]["misses"]

    second_rc, second = _run_capture(tmp_path, "--cache-stats")
    assert second_rc in {0, 1}
    assert second["summary"]["cache"]["hits"]
    assert not second["summary"]["cache"]["misses"]

    untracked = tmp_path / "untracked.txt"
    untracked.write_text("hi\n", encoding="utf-8")

    third_rc, third = _run_capture(tmp_path, "--cache-stats")
    assert third_rc in {0, 1}
    assert third["summary"]["cache"]["hits"]
    assert not third["summary"]["cache"]["misses"]

    untracked.write_text("bye\n", encoding="utf-8")

    fourth_rc, fourth = _run_capture(tmp_path, "--cache-stats")
    assert fourth_rc in {0, 1}
    assert fourth["summary"]["cache"]["hits"]
    assert not fourth["summary"]["cache"]["misses"]


def test_cache_invalidates_on_content_change_even_when_mtime_restored(tmp_path: Path) -> None:
    _seed_repo(tmp_path)

    first_rc, first = _run_capture(tmp_path, "--cache-stats")
    assert first_rc in {0, 1}
    assert first["summary"]["cache"]["misses"]

    second_rc, second = _run_capture(tmp_path, "--cache-stats")
    assert second_rc in {0, 1}
    assert second["summary"]["cache"]["hits"]

    readme = tmp_path / "README.md"
    old = readme.read_text(encoding="utf-8")
    assert old

    st = readme.stat()
    mtime_ns = st.st_mtime_ns

    if len(old) == 1:
        new = "Y" if old != "Y" else "Z"
    else:
        head = "Y" if old[0] != "Y" else "Z"
        new = head + old[1:]
    assert new != old
    assert len(new.encode("utf-8")) == len(old.encode("utf-8"))

    readme.write_text(new, encoding="utf-8")
    os.utime(readme, ns=(mtime_ns, mtime_ns))

    third_rc, third = _run_capture(tmp_path, "--cache-stats")
    assert third_rc in {0, 1}
    assert third["summary"]["cache"]["misses"]


def test_deps_cache_survives_tracked_change_that_is_not_a_dependency(tmp_path: Path) -> None:
    _seed_repo(tmp_path)

    rc1, first = _run_capture(tmp_path, "--cache-stats", "--cache-strategy", "deps")
    assert rc1 in {0, 1}
    assert first["summary"]["cache"]["misses"]

    rc2, second = _run_capture(tmp_path, "--cache-stats", "--cache-strategy", "deps")
    assert rc2 in {0, 1}
    assert second["summary"]["cache"]["hits"]
    assert not second["summary"]["cache"]["misses"]

    readme = tmp_path / "README.md"
    readme.write_text("# changed\n", encoding="utf-8")

    rc3, third = _run_capture(tmp_path, "--cache-stats", "--cache-strategy", "deps")
    assert rc3 in {0, 1}
    assert third["summary"]["cache"]["hits"]
    assert not third["summary"]["cache"]["misses"]

    rc4, tree = _run_capture(tmp_path, "--cache-stats")
    assert rc4 in {0, 1}
    assert tree["summary"]["cache"]["misses"]
    assert not tree["summary"]["cache"]["hits"]
