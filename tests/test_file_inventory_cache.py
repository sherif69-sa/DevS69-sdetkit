from __future__ import annotations

import json
import os
from pathlib import Path

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


def _inv_paths(inv: list[object]) -> list[str]:
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
