from __future__ import annotations

from pathlib import Path

import pytest

import sdetkit.atomicio as atomicio
from sdetkit.atomicio import atomic_write_bytes


def test_atomic_write_bytes_before_replace_hook_runs(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    seen = {"called": 0}

    def hook(tmp: Path, final: Path) -> None:
        assert tmp.exists()
        assert final == target
        seen["called"] += 1

    atomic_write_bytes(target, b"x", before_replace=hook)
    assert seen["called"] == 1
    assert target.read_bytes() == b"x"


def test_atomic_write_bytes_dir_fsync_fail_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.bin"
    real_open = atomicio.os.open

    def guarded_open(path: str, flags: int, *args: object, **kwargs: object) -> int:
        if flags & getattr(atomicio.os, "O_DIRECTORY", 0):
            raise OSError("no dir fd")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(atomicio.os, "open", guarded_open)

    atomic_write_bytes(target, b"abc")
    assert target.read_bytes() == b"abc"


def test_atomic_write_bytes_cleanup_unlink_error_is_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Boom(Exception):
        pass

    target = tmp_path / "out.bin"
    target.write_bytes(b"old")

    def boom_replace(*_a: object, **_k: object) -> None:
        raise Boom("boom")

    def boom_unlink(self: Path, *_a: object, **_k: object) -> None:
        raise OSError("unlink boom")

    import pathlib

    monkeypatch.setattr(atomicio.os, "replace", boom_replace)
    monkeypatch.setattr(pathlib.Path, "unlink", boom_unlink)

    with pytest.raises(Boom, match="boom"):
        atomic_write_bytes(target, b"new")

    assert target.read_bytes() == b"old"
