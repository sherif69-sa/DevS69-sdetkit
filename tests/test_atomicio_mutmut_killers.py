import locale

import pytest

import sdetkit.atomicio as atomicio
from sdetkit.atomicio import atomic_write_text


def test_atomic_write_text_creates_nested_parents_and_writes(tmp_path):
    target = tmp_path / "a" / "b" / "c" / "out.txt"
    atomic_write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_text_mkdir_uses_parents_true_and_exist_ok_true(tmp_path, monkeypatch):
    target = tmp_path / "a" / "b" / "c" / "out.txt"
    parent = target.parent

    calls = []
    cls = type(parent)
    orig = cls.mkdir

    def mkdir_wrapped(self, *args, **kwargs):
        calls.append((self, args, kwargs.copy()))
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(cls, "mkdir", mkdir_wrapped)

    atomic_write_text(target, "x")

    allowed = set()
    cur = parent
    for _ in range(32):
        allowed.add(cur)
        nxt = cur.parent
        if nxt == cur:
            break
        cur = nxt

    hits = []
    for pp, args, kw in calls:
        if pp not in allowed:
            continue
        parents = kw.get("parents", args[1] if len(args) > 1 else False)
        exist_ok = kw.get("exist_ok", args[2] if len(args) > 2 else False)
        if parents is True and exist_ok is True:
            hits.append((pp, args, kw))

    assert hits


def test_atomic_write_text_uses_utf8_even_under_C_locale(tmp_path):
    orig = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        target = tmp_path / "out.txt"
        text = "café"
        atomic_write_text(target, text)
        assert target.read_bytes() == text.encode("utf-8")
    finally:
        locale.setlocale(locale.LC_ALL, orig)


def test_atomic_write_text_mkstemp_uses_prefix_and_dir(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"
    parent = target.parent

    calls = []
    orig = atomicio.tempfile.mkstemp

    def mkstemp_wrapped(*args, **kwargs):
        calls.append((args, kwargs.copy()))
        return orig(*args, **kwargs)

    monkeypatch.setattr(atomicio.tempfile, "mkstemp", mkstemp_wrapped)

    atomic_write_text(target, "x")

    assert calls
    _args, kw = calls[-1]
    assert "dir" in kw
    assert kw["dir"] == str(parent)
    assert "prefix" in kw
    assert kw["prefix"] == target.name + "."


def test_atomic_write_text_fdopen_uses_utf8_and_newline_empty(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"

    calls = []
    orig = atomicio.os.fdopen

    def fdopen_wrapped(fd, mode="r", *args, **kwargs):
        calls.append((mode, args, kwargs.copy()))
        return orig(fd, mode, *args, **kwargs)

    monkeypatch.setattr(atomicio.os, "fdopen", fdopen_wrapped)

    atomic_write_text(target, "x")

    w_calls = [c for c in calls if c[0].startswith("w")]
    assert w_calls
    _mode, _args, kw = w_calls[-1]
    assert "encoding" in kw
    assert kw["encoding"] == "utf-8"
    assert "newline" in kw
    assert kw["newline"] == ""


def test_atomic_write_text_opens_parent_dir_with_O_DIRECTORY_and_fsyncs(tmp_path, monkeypatch):
    if not hasattr(atomicio.os, "O_DIRECTORY"):
        pytest.skip("os.O_DIRECTORY not available")

    target = tmp_path / "out.txt"
    parent = target.parent

    open_records = []
    fsync_calls = []

    orig_open = atomicio.os.open

    def open_wrapped(*args, **kwargs):
        try:
            fd = orig_open(*args, **kwargs)
        except Exception as e:
            open_records.append(("err", args, kwargs.copy(), type(e)))
            raise
        else:
            open_records.append(("ok", args, kwargs.copy(), fd))
            return fd

    def fsync_wrapped(fd):
        fsync_calls.append(fd)
        return None

    monkeypatch.setattr(atomicio.os, "open", open_wrapped)
    monkeypatch.setattr(atomicio.os, "fsync", fsync_wrapped)

    atomic_write_text(target, "x")

    good = [
        r for r in open_records if r[0] == "ok" and r[1] == (str(parent), atomicio.os.O_DIRECTORY)
    ]
    assert good
    dir_fd = good[-1][3]
    assert dir_fd in fsync_calls


def test_atomic_write_text_preserves_original_if_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")

    def replace_fail(src, dst):
        raise RuntimeError("boom")

    monkeypatch.setattr(atomicio.os, "replace", replace_fail)

    with pytest.raises(RuntimeError):
        atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "old"


def test_atomic_write_text_leaves_no_extra_files(tmp_path):
    target = tmp_path / "out.txt"
    atomic_write_text(target, "x")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.txt"]


def test_atomic_write_text_cleanup_unlink_error_is_swallowed(tmp_path, monkeypatch):
    import pathlib

    import pytest

    import sdetkit.atomicio as atomicio

    class Boom(Exception):
        pass

    def boom_replace(*_a, **_k):
        raise Boom("boom")

    def boom_unlink(self, *_a, **_k):
        raise OSError("unlink boom")

    monkeypatch.setattr(atomicio.os, "replace", boom_replace)
    monkeypatch.setattr(pathlib.Path, "unlink", boom_unlink)

    with pytest.raises(Boom) as ei:
        atomicio.atomic_write_text(tmp_path / "out.txt", "x")

    assert str(ei.value) == "boom"
