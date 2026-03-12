from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from sdetkit.repo import _FileInventoryCache


def _write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8", newline="\n")


def test_file_inventory_cache_hit_and_invalidation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _write(repo / "a.py", "print('a')\n")
    _write(repo / "pkg" / "b.py", "x = 1\n")

    cache_root = tmp_path / "cache"
    c = _FileInventoryCache(cache_root)

    inv1 = c.get_inventory(repo)
    s1 = c.stats()
    assert s1 == {"hits": 0, "misses": 1, "writes": 1, "invalidations": 0}

    inv1d = [f.to_dict() for f in inv1]
    paths1 = [d["path"] for d in inv1d]
    assert paths1 == sorted(paths1)

    cache_files = sorted(cache_root.rglob("*.json"))
    assert cache_files
    raw = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert isinstance(raw["dirs"], list)
    assert isinstance(raw["files"], list)

    inv2 = c.get_inventory(repo)
    assert _inv_paths(inv2) == _inv_paths(inv1)
    s2 = c.stats()
    assert s2 == {"hits": 1, "misses": 1, "writes": 1, "invalidations": 0}

    _write(repo / "pkg" / "b.py", "x = 2\n")
    inv3 = c.get_inventory(repo)
    s3 = c.stats()
    assert s3["invalidations"] >= 1
    assert s3["writes"] >= 2
    assert any(d["path"] == "pkg/b.py" for d in [f.to_dict() for f in inv3])

    _write(repo / "pkg" / "c.py", "y = 3\n")
    inv4 = c.get_inventory(repo)
    s4 = c.stats()
    assert s4["invalidations"] >= 2
    assert s4["writes"] >= 3
    paths4 = [d["path"] for d in [f.to_dict() for f in inv4]]
    assert "pkg/c.py" in paths4


def _inv_paths(inv: Sequence[object]) -> list[str]:
    out: list[str] = []
    for fi in inv:
        out.append(str(getattr(fi, "path", getattr(fi, "rel_path", ""))))
    return sorted(out)


def _stats_dict(cache: object) -> dict[str, int]:
    if hasattr(cache, "stats"):
        try:
            st = cache.stats()
            if isinstance(st, dict):
                return {str(k): int(v) for k, v in st.items()}
        except TypeError:
            pass
    st2 = getattr(cache, "_stats", None)
    if isinstance(st2, dict):
        return {str(k): int(v) for k, v in st2.items()}
    raise AssertionError("cache has no stats dict")


def test_file_inventory_cache_corrupt_cache_treated_as_miss(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "a.py", "print('a')\n")
    _write(repo / "pkg" / "b.py", "x = 1\n")

    cache_root = tmp_path / "cache"
    c = _FileInventoryCache(cache_root)

    inv1 = c.get_inventory(repo)
    before = _stats_dict(c)

    cache_path = c._path_for_root(repo)
    cache_path.write_text("{not valid json", encoding="utf-8")

    c.get_inventory(repo)
    after = _stats_dict(c)

    assert _inv_paths(c.get_inventory(repo)) == _inv_paths(inv1)
    assert after.get("misses", 0) >= before.get("misses", 0) + 1


def test_file_inventory_cache_add_file_invalidates_and_updates(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "a.py", "print('a')\n")
    _write(repo / "pkg" / "b.py", "x = 1\n")

    cache_root = tmp_path / "cache"
    c = _FileInventoryCache(cache_root)

    inv1 = c.get_inventory(repo)
    st1 = _stats_dict(c)

    assert _inv_paths(c.get_inventory(repo)) == _inv_paths(inv1)
    st2 = _stats_dict(c)
    assert _inv_paths(c.get_inventory(repo)) == _inv_paths(inv1)
    assert st2.get("hits", 0) >= st1.get("hits", 0) + 1

    _write(repo / "pkg" / "c.py", "y = 2\n")
    inv3 = c.get_inventory(repo)
    st3 = _stats_dict(c)

    assert "pkg/c.py" in _inv_paths(inv3)
    assert st3.get("invalidations", 0) >= st2.get("invalidations", 0) + 1

    inv4 = c.get_inventory(repo)
    st4 = _stats_dict(c)
    assert _inv_paths(inv4) == _inv_paths(inv3)
    assert st4.get("hits", 0) >= st3.get("hits", 0) + 1


def test_file_inventory_cache_remove_file_invalidates_and_updates(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "a.py", "print('a')\n")
    _write(repo / "pkg" / "b.py", "x = 1\n")

    cache_root = tmp_path / "cache"
    c = _FileInventoryCache(cache_root)

    inv1 = c.get_inventory(repo)
    st1 = _stats_dict(c)
    assert "pkg/b.py" in _inv_paths(inv1)

    c.get_inventory(repo)
    st2 = _stats_dict(c)
    assert st2.get("hits", 0) >= st1.get("hits", 0) + 1

    (repo / "pkg" / "b.py").unlink()
    inv3 = c.get_inventory(repo)
    st3 = _stats_dict(c)

    assert "pkg/b.py" not in _inv_paths(inv3)
    assert st3.get("invalidations", 0) >= st2.get("invalidations", 0) + 1


def test_file_inventory_cache_skips_expensive_strict_scan_for_large_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sdetkit import repo as repo_mod

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "pkg" / "a.py", "print('a')\n")

    cache = repo_mod._FileInventoryCache(tmp_path / "cache")
    inv = cache.get_inventory(repo)

    monkeypatch.setenv("SDETKIT_INVENTORY_STRICT_MAX_FILES", "0")

    called = {"count": 0}

    def _explode(_root: Path) -> list[Path]:
        called["count"] += 1
        raise AssertionError("_iter_files should not be called when strict scan is disabled")

    monkeypatch.setattr(repo_mod, "_iter_files", _explode)

    assert cache._validate_files(repo, inv) is True
    assert called["count"] == 0


def test_file_inventory_cache_invalid_strict_scan_env_falls_back_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sdetkit import repo as repo_mod

    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "pkg" / "a.py", "print('a')\n")

    cache = repo_mod._FileInventoryCache(tmp_path / "cache")
    inv = cache.get_inventory(repo)

    monkeypatch.setenv("SDETKIT_INVENTORY_STRICT_MAX_FILES", "not-an-int")

    called = {"count": 0}
    original = repo_mod._iter_files

    def _tracked(root: Path) -> list[Path]:
        called["count"] += 1
        return original(root)

    monkeypatch.setattr(repo_mod, "_iter_files", _tracked)

    assert cache._validate_files(repo, inv) is True
    assert called["count"] >= 1


def test_file_inventory_cache_add_file_detected_when_dir_mtime_is_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "pkg" / "a.py", "print('a')\n")

    cache_root = tmp_path / "cache"
    c = _FileInventoryCache(cache_root)

    c.get_inventory(repo)
    pkg = repo / "pkg"
    original = pkg.stat()

    _write(repo / "pkg" / "new.py", "print('new')\n")
    os.utime(pkg, ns=(original.st_atime_ns, original.st_mtime_ns))

    updated = c.get_inventory(repo)
    assert "pkg/new.py" in _inv_paths(updated)


def test_inventory_strict_max_files_resolution_prefers_cli_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdetkit import repo as repo_mod

    monkeypatch.setenv(repo_mod.INVENTORY_STRICT_MAX_FILES_ENV, "123")
    assert repo_mod._resolve_inventory_strict_max_files(7) == 7
    assert repo_mod._resolve_inventory_strict_max_files(None) == 123

    monkeypatch.setenv(repo_mod.INVENTORY_STRICT_MAX_FILES_ENV, "bad")
    assert (
        repo_mod._resolve_inventory_strict_max_files(None)
        == repo_mod.INVENTORY_STRICT_MAX_FILES_DEFAULT
    )


def test_repo_helpers_and_fileinfo_type_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sdetkit import repo as repo_mod

    assert repo_mod._safe_snippet("short") == "<redacted>"
    assert repo_mod._safe_snippet("abcdefghijk") == "abc...ijk"
    assert repo_mod._shannon_entropy("") == 0.0

    with pytest.raises(TypeError):
        repo_mod.FileInfo.from_dict({"path": 1, "mtime_ns": 1, "size": 1})
    with pytest.raises(TypeError):
        repo_mod.FileInfo.from_dict({"path": "a", "mtime_ns": "1", "size": 1})
    with pytest.raises(TypeError):
        repo_mod.FileInfo.from_dict({"path": "a", "mtime_ns": 1, "size": "1"})
    with pytest.raises(TypeError):
        repo_mod.FileInfo.from_dict({"path": "a", "mtime_ns": 1, "size": 1, "ctime_ns": "1"})

    info = repo_mod.FileInfo.from_dict({"path": "a.py", "mtime_ns": 1, "size": 2})
    assert info.rel_path == "a.py"
    assert info.to_dict()["ctime_ns"] == -1

    class _Proc:
        def __init__(self, returncode: int, stdout: str) -> None:
            self.returncode = returncode
            self.stdout = stdout

    monkeypatch.setattr(repo_mod.subprocess, "run", lambda *a, **k: _Proc(0, "abc123\n"))
    assert repo_mod._git_commit_sha(tmp_path) == "abc123"

    monkeypatch.setattr(repo_mod.subprocess, "run", lambda *a, **k: _Proc(1, ""))
    assert repo_mod._git_commit_sha(tmp_path) is None

    def _boom(*_a, **_k):
        raise OSError("no git")

    monkeypatch.setattr(repo_mod.subprocess, "run", _boom)
    assert repo_mod._git_commit_sha(tmp_path) is None
    assert repo_mod._changed_files(tmp_path, "HEAD~1") == set()


def test_iter_files_and_load_cache_invalid_shapes(tmp_path: Path) -> None:
    from sdetkit import repo as repo_mod

    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "ok.py", "print('ok')\n")
    _write(root / ".coverage", "x")
    _write(root / "node_modules" / "skip.js", "x")
    _write(root / "pkg.egg-info" / "PKG-INFO", "x")

    files = repo_mod._iter_files(root)
    rels = [f.relative_to(root).as_posix() for f in files]
    assert rels == ["ok.py"]

    cache = repo_mod._FileInventoryCache(tmp_path / "cache")
    cache_path = cache._path_for_root(root)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    for payload in [
        [],
        "bad",
        {"schema_version": 2, "dirs": [], "files": []},
        {"schema_version": 1, "dirs": "bad", "files": []},
        {"schema_version": 1, "dirs": [], "files": "bad"},
        {"schema_version": 1, "dirs": ["x"], "files": []},
        {"schema_version": 1, "dirs": [{"path": 1, "mtime_ns": 1}], "files": []},
        {"schema_version": 1, "dirs": [{"path": ".", "mtime_ns": 1}], "files": ["x"]},
    ]:
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        assert cache._load_cache(cache_path) is None


def test_cache_validate_and_digest_variants(tmp_path: Path) -> None:
    from sdetkit import repo as repo_mod

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(repo_root / "pkg" / "a.py", "print('a')\n")

    cache = repo_mod._FileInventoryCache(tmp_path / "cache")
    cache.get_inventory(repo_root)

    assert cache._validate_dirs(repo_root, {"missing": 0}) is False
    assert cache._validate_files(repo_root, [repo_mod.FileInfo("missing.py", 1, 1, -1)]) is False

    one = cache.digest_for(repo_root)
    two = cache.digest_for(repo_root)
    assert one == two

    digest_missing = cache.digest_for(repo_root, "does/not/exist.py")
    assert isinstance(digest_missing, str)
    assert len(digest_missing) == 64

    tree_digest = cache.digest_for(repo_root, "__repo_tree__")
    assert isinstance(tree_digest, str)
    assert len(tree_digest) == 64
