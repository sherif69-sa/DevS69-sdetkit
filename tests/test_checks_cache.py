from __future__ import annotations

from pathlib import Path

from sdetkit.checks.cache import CheckCache


def test_compute_repo_fingerprint_tracks_directory_targets(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pkg = repo_root / "src" / "pkg"
    pkg.mkdir(parents=True)
    target = pkg / "module.py"
    target.write_text("value = 1\n", encoding="utf-8")

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    before = cache.compute_repo_fingerprint(repo_root, ("src/pkg",))

    target.write_text("value = 2\n", encoding="utf-8")
    cache = CheckCache(tmp_path / ".sdetkit-cache")
    after = cache.compute_repo_fingerprint(repo_root, ("src/pkg",))

    assert before != after


def test_compute_repo_fingerprint_ignores_tooling_cache_with_directory_targets(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = repo_root / ".sdetkit" / "out"
    out_dir.mkdir(parents=True)
    noisy = out_dir / "run.json"
    noisy.write_text('{"v": 1}\n', encoding="utf-8")

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    before = cache.compute_repo_fingerprint(repo_root, (".sdetkit",))

    noisy.write_text('{"v": 2}\n', encoding="utf-8")
    cache = CheckCache(tmp_path / ".sdetkit-cache")
    after = cache.compute_repo_fingerprint(repo_root, (".sdetkit",))

    assert before == after


def test_compute_repo_fingerprint_ignores_venv_directory_targets(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    venv_dir = repo_root / ".venv"
    venv_dir.mkdir(parents=True)
    noisy = venv_dir / "state.txt"
    noisy.write_text("v1\n", encoding="utf-8")

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    before = cache.compute_repo_fingerprint(repo_root, (".venv",))

    noisy.write_text("v2\n", encoding="utf-8")
    cache = CheckCache(tmp_path / ".sdetkit-cache")
    after = cache.compute_repo_fingerprint(repo_root, (".venv",))

    assert before == after


def test_compute_repo_fingerprint_ignores_outside_repo_hint_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "tracked.txt").write_text("ok\n", encoding="utf-8")

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    inside_only = cache.compute_repo_fingerprint(repo_root, ("tracked.txt",))

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    with_outside_hint = cache.compute_repo_fingerprint(repo_root, ("../outside", "tracked.txt"))

    assert inside_only == with_outside_hint


def test_compute_repo_fingerprint_ignores_absolute_outside_repo_hint_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "tracked.txt").write_text("ok\n", encoding="utf-8")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("nope\n", encoding="utf-8")

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    inside_only = cache.compute_repo_fingerprint(repo_root, ("tracked.txt",))

    cache = CheckCache(tmp_path / ".sdetkit-cache")
    with_outside_hint = cache.compute_repo_fingerprint(
        repo_root, (str(outside_file), "tracked.txt")
    )

    assert inside_only == with_outside_hint


def test_compute_repo_fingerprint_survives_a_dangling_symlink(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo_root / "dangling").symlink_to(repo_root / "missing")

    fingerprint = CheckCache(tmp_path / ".sdetkit-cache").compute_repo_fingerprint(repo_root, ())

    assert len(fingerprint) == 64


def test_compute_repo_fingerprint_changes_with_a_commit_outside_the_changed_set(
    tmp_path: Path,
) -> None:
    import subprocess

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    (repo_root / "x.py").write_text("x = 1\n", encoding="utf-8")
    (repo_root / "y.py").write_text("y = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    (repo_root / "x.py").write_text("x = 2\n", encoding="utf-8")
    before = CheckCache(tmp_path / "c").compute_repo_fingerprint(repo_root, ("x.py",))

    (repo_root / "y.py").write_text("y = 'lint error' +\n", encoding="utf-8")
    git("commit", "-qam", "touch y")
    (repo_root / "x.py").write_text("x = 2\n", encoding="utf-8")
    after = CheckCache(tmp_path / "c").compute_repo_fingerprint(repo_root, ("x.py",))

    assert before != after
