import threading
from pathlib import Path

from sdetkit.atomicio import atomic_write_text


def test_atomic_write_text_writes_exact_content(tmp_path):
    p = tmp_path / "out.txt"
    atomic_write_text(p, "hello\n")
    assert p.read_text(encoding="utf-8") == "hello\n"


def test_atomic_write_text_is_atomic_for_readers(tmp_path):
    p = tmp_path / "out.txt"
    atomic_write_text(p, "start\n")

    stop = threading.Event()
    bad = {"n": 0}

    def reader():
        while not stop.is_set():
            t = p.read_text(encoding="utf-8")
            if t not in ("start\n", "A\n", "B\n"):
                bad["n"] += 1
                stop.set()

    th = threading.Thread(target=reader, daemon=True)
    th.start()

    for _ in range(200):
        atomic_write_text(p, "A\n")
        atomic_write_text(p, "B\n")

    stop.set()
    th.join(timeout=1)
    assert bad["n"] == 0


def test_atomic_write_text_before_replace_hook_runs(tmp_path):
    p = tmp_path / "out.txt"
    seen = {"called": 0}

    def hook(tmp: Path, final: Path):
        assert tmp.exists()
        assert final == p
        seen["called"] += 1

    atomic_write_text(p, "x\n", before_replace=hook)
    assert seen["called"] == 1


def test_atomic_write_text_does_not_modify_final_before_replace(tmp_path):
    from pathlib import Path

    p = tmp_path / "out.txt"
    p.write_text("old\n", encoding="utf-8")

    seen = {"called": 0}

    def hook(tmp: Path, final: Path):
        assert final.read_text(encoding="utf-8") == "old\n"
        assert tmp.parent == final.parent
        seen["called"] += 1

    atomic_write_text(p, "new\n", before_replace=hook)
    assert seen["called"] == 1
    assert p.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_dir_fsync_fail_is_ignored(tmp_path, monkeypatch):
    import os as _os

    p = tmp_path / "out.txt"
    real_open = _os.open

    def guarded_open(path, flags, *args, **kwargs):
        if flags & getattr(_os, "O_DIRECTORY", 0):
            raise OSError("no dir fd")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(_os, "open", guarded_open)
    atomic_write_text(p, "x\n")
    assert p.read_text(encoding="utf-8") == "x\n"


def test_atomic_write_text_cleans_temp_on_hook_error(tmp_path):
    from pathlib import Path

    p = tmp_path / "out.txt"
    p.write_text("old\n", encoding="utf-8")

    before = sorted(x.name for x in tmp_path.iterdir())

    def hook(tmp: Path, final: Path):
        raise RuntimeError("boom")

    try:
        atomic_write_text(p, "new\n", before_replace=hook)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")

    after = sorted(x.name for x in tmp_path.iterdir())
    assert before == after
    assert p.read_text(encoding="utf-8") == "old\n"
