from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sdetkit.utils import atomicio
from sdetkit.utils.textutil import DuplicateKeyError, parse_kv_line


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_nested_atomic_write_preserves_payload_and_same_directory(tmp_path, kind):
    target = tmp_path / "nested" / "parent" / "out"
    payload = "caf\u00e9\r\n\u0645\u0631\u062d\u0628\u0627\n" if kind == "text" else b"\x00\xff\r\n"
    expected = payload.encode("utf-8") if kind == "text" else payload
    seen = []

    def hook(temporary, final):
        assert final == target
        assert temporary.parent == target.parent
        assert temporary != final
        assert temporary.read_bytes() == expected
        assert not final.exists()
        seen.append(temporary)

    getattr(atomicio, f"atomic_write_{kind}")(target, payload, before_replace=hook)
    assert target.read_bytes() == expected
    assert len(seen) == 1
    assert not seen[0].exists()
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_atomic_write_syncs_file_before_replace_and_directory_after(tmp_path, monkeypatch, kind):
    target = tmp_path / "out"
    events = []
    real_fsync, real_open, real_close, real_replace = os.fsync, os.open, os.close, os.replace
    directory_fds = set()

    def open_directory(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        if flags & os.O_DIRECTORY:
            assert Path(path) == tmp_path
            directory_fds.add(fd)
            events.append("directory-open")
        return fd

    def sync(fd):
        events.append("directory-sync" if fd in directory_fds else "file-sync")
        return real_fsync(fd)

    def close(fd):
        if fd in directory_fds:
            events.append("directory-close")
        return real_close(fd)

    def replace(source, destination):
        events.append("replace")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "open", open_directory)
    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "close", close)
    monkeypatch.setattr(os, "replace", replace)
    getattr(atomicio, f"atomic_write_{kind}")(target, "new" if kind == "text" else b"new")
    assert events == ["file-sync", "replace", "directory-open", "directory-sync", "directory-close"]


@pytest.mark.parametrize("kind", ["text", "bytes"])
@pytest.mark.parametrize("failure", ["hook", "replace", "file-sync"])
def test_atomic_write_failure_preserves_old_file_and_cleans_temp(
    tmp_path, monkeypatch, kind, failure
):
    target = tmp_path / "out"
    target.write_bytes(b"old")

    def fail(*args):
        raise OSError("injected failure")

    hook = fail if failure == "hook" else None
    if failure == "replace":
        monkeypatch.setattr(os, "replace", fail)
    elif failure == "file-sync":
        monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="injected failure"):
        getattr(atomicio, f"atomic_write_{kind}")(
            target, "new" if kind == "text" else b"new", before_replace=hook
        )
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_directory_sync_failure_closes_descriptor(tmp_path, monkeypatch, kind):
    real_open, real_fsync, real_close = os.open, os.fsync, os.close
    directory_fds, closed = set(), []

    def open_directory(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        if flags & os.O_DIRECTORY:
            directory_fds.add(fd)
        return fd

    def sync(fd):
        if fd in directory_fds:
            raise OSError("directory sync failed")
        return real_fsync(fd)

    def close(fd):
        if fd in directory_fds:
            closed.append(fd)
        return real_close(fd)

    monkeypatch.setattr(os, "open", open_directory)
    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "close", close)
    target = tmp_path / "out"
    with pytest.raises(OSError, match="directory sync failed"):
        getattr(atomicio, f"atomic_write_{kind}")(target, "new" if kind == "text" else b"new")
    assert len(closed) == 1
    assert set(closed) == directory_fds
    assert target.read_bytes() == b"new"
    assert list(tmp_path.iterdir()) == [target]


def test_canonical_json_text_is_sorted_ascii_and_newline_terminated():
    payload = {"z": [True, None], "a": "\u00e9"}
    expected = '{\n  "a": "\\u00e9",\n  "z": [\n    true,\n    null\n  ]\n}\n'
    assert atomicio.canonical_json_dumps(payload) == expected
    assert (
        atomicio.canonical_json_dumps(payload, indent=None)
        == '{"a": "\\u00e9", "z": [true, null]}\n'
    )
    assert (
        atomicio.canonical_json_dumps({"z": 1, "a": 2}, indent=4)
        == '{\n    "a": 2,\n    "z": 1\n}\n'
    )


def test_canonical_json_bytes_is_compact_sorted_ascii_without_newline():
    payload = {"z": [True, None], "a": "\u00e9"}
    encoded = atomicio.canonical_json_bytes(payload)
    assert encoded == b'{"a":"\\u00e9","z":[true,null]}'
    assert json.loads(encoded) == payload


@pytest.mark.parametrize("comments", [False, True])
def test_parser_preserves_quoted_hash_equals_spaces_and_uppercase_x(comments):
    line = 'name="X value=#tag" other=a=b marker=X'
    if comments:
        line += " # ignored=comment"
    assert parse_kv_line(line, allow_comments=comments) == {
        "name": "X value=#tag",
        "other": "a=b",
        "marker": "X",
    }


def test_duplicate_error_policy_accepts_distinct_keys_before_rejecting_repeat():
    assert parse_kv_line("a=1 b=2", duplicate_policy="error") == {"a": "1", "b": "2"}
    with pytest.raises(DuplicateKeyError):
        parse_kv_line("a=1 b=2 a=3", duplicate_policy="error")


@pytest.mark.parametrize("line", ["", "a=1"])
def test_invalid_policy_is_rejected_even_for_empty_input(line):
    with pytest.raises(ValueError):
        parse_kv_line(line, duplicate_policy="unknown")


@pytest.mark.parametrize("comments", [False, True])
@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("a=1 broken", "bad token"),
        ("XXXX", "bad token"),
        ("=value", "bad kv"),
        ("key=", "bad kv"),
        ('key=""', "bad kv"),
    ],
)
def test_parser_malformed_tokens_have_stable_diagnostics(comments, line, message):
    with pytest.raises(ValueError) as error:
        parse_kv_line(line, allow_comments=comments)
    assert type(error.value) is ValueError
    assert error.value.args == (message,)


@pytest.mark.parametrize("line", ["", "a=1"])
def test_invalid_policy_diagnostic_precedes_parsing(line):
    with pytest.raises(ValueError) as error:
        parse_kv_line(line, duplicate_policy="unknown")
    assert error.value.args == ("bad duplicate policy",)


@pytest.mark.parametrize("comments", [False, True])
def test_duplicate_diagnostic_keeps_exact_case_sensitive_key(comments):
    with pytest.raises(DuplicateKeyError) as error:
        parse_kv_line(
            "Name=one name=two Name=three", allow_comments=comments, duplicate_policy="error"
        )
    assert error.value.args == ("duplicate key: Name",)


@pytest.mark.parametrize("policy", ["first", "last", "error"])
def test_parser_comment_only_line_is_empty_under_every_duplicate_policy(policy):
    assert parse_kv_line("  # not-a-token key=", allow_comments=True, duplicate_policy=policy) == {}


@pytest.mark.parametrize("kind", ["text", "bytes"])
@pytest.mark.parametrize("cleanup_operation", ["exists", "unlink"])
def test_cleanup_failure_does_not_mask_original_error(
    tmp_path, monkeypatch, caplog, kind, cleanup_operation
):
    import logging

    target = tmp_path / "out"
    target.write_bytes(b"old")
    original = RuntimeError("original write failure")
    cleanup = OSError("cleanup failure")
    temporary_paths = []
    real_operation = getattr(Path, cleanup_operation)

    def fail_cleanup(path, *args, **kwargs):
        if path in temporary_paths:
            raise cleanup
        return real_operation(path, *args, **kwargs)

    def fail_before_replace(temporary, final):
        assert final == target
        temporary_paths.append(temporary)
        raise original

    monkeypatch.setattr(Path, cleanup_operation, fail_cleanup)
    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError) as error:
        getattr(atomicio, f"atomic_write_{kind}")(
            target, "new" if kind == "text" else b"new", before_replace=fail_before_replace
        )
    assert error.value is original
    assert target.read_bytes() == b"old"
    assert len(temporary_paths) == 1
    records = [record for record in caplog.records if record.levelno == logging.DEBUG]
    assert len(records) == 1
    assert records[0].args == (temporary_paths[0], cleanup)
    assert records[0].getMessage() == (
        f"Failed to remove temporary file {temporary_paths[0]}: cleanup failure"
    )
    monkeypatch.undo()
    assert temporary_paths[0].exists()
    temporary_paths[0].unlink()


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_directory_open_unavailable_keeps_completed_write(tmp_path, monkeypatch, kind):
    target = tmp_path / "out"
    real_open = os.open
    directory_attempts = []

    def open_without_directory_support(path, flags, *args, **kwargs):
        if flags & os.O_DIRECTORY:
            directory_attempts.append(path)
            raise OSError("directory sync unavailable")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_without_directory_support)
    getattr(atomicio, f"atomic_write_{kind}")(target, "new" if kind == "text" else b"new")
    assert target.read_bytes() == b"new"
    assert directory_attempts == [str(tmp_path)]
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_atomic_write_closes_descriptor_when_stream_open_fails(tmp_path, monkeypatch, kind):
    import errno

    target = tmp_path / "out"
    target.write_bytes(b"old")
    descriptors = []
    original = OSError("stream creation failed")

    def fail_fdopen(fd, *args, **kwargs):
        descriptors.append(fd)
        raise original

    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    with pytest.raises(OSError) as error:
        getattr(atomicio, f"atomic_write_{kind}")(target, "new" if kind == "text" else b"new")
    assert error.value is original
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]
    assert len(descriptors) == 1
    try:
        with pytest.raises(OSError) as closed:
            os.fstat(descriptors[0])
        assert closed.value.errno == errno.EBADF
    finally:
        # The before-fix test must not leak its deliberately exposed descriptor.
        try:
            os.close(descriptors[0])
        except OSError:
            pass


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_descriptor_close_error_does_not_mask_stream_open_error(tmp_path, monkeypatch, kind):
    target = tmp_path / "out"
    original = OSError("stream creation failed")
    real_close = os.close
    closed = []

    def fail_fdopen(fd, *args, **kwargs):
        raise original

    def close_then_fail(fd):
        real_close(fd)
        closed.append(fd)
        raise OSError("close failed")

    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    monkeypatch.setattr(os, "close", close_then_fail)
    with pytest.raises(OSError) as error:
        getattr(atomicio, f"atomic_write_{kind}")(target, "new" if kind == "text" else b"new")
    assert error.value is original
    assert len(closed) == 1
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
