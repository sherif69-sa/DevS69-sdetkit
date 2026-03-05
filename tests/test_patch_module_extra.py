from __future__ import annotations

import errno
from pathlib import Path

import pytest

import sdetkit.patch as patch


def test_patch_ops_replace_and_insert_variants(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("A\nB\nC\n", encoding="utf-8")

    old, new = patch.apply_ops(
        f,
        [
            {"op": "insert_before", "pattern": r"^B$", "text": "X\n"},
            {"op": "replace_once", "pattern": r"^C$", "repl": "D"},
        ],
    )
    assert old == "A\nB\nC\n"
    assert new == "A\nX\nB\nD\n"


def test_patch_replace_block_and_insert_fallback(tmp_path: Path):
    f = tmp_path / "b.txt"
    f.write_text("start\nkeep\nend\n", encoding="utf-8")

    _, replaced = patch.apply_ops(
        f,
        [
            {
                "op": "replace_block",
                "start": r"^start$",
                "end": r"^end$",
                "text": "start\nnew\n",
            }
        ],
    )
    assert replaced == "start\nnew\nend\n"

    _, inserted = patch.apply_ops(
        f,
        [
            {
                "op": "replace_or_insert_block",
                "start": r"^missing-start$",
                "end": r"^missing-end$",
                "insert_after": r"^start$",
                "text": "added\n",
            }
        ],
    )
    assert inserted == "start\nadded\nkeep\nend\n"


def test_patch_upsert_def_class_and_method(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text(
        "class A:\n    def f(self):\n        return 1\n",
        encoding="utf-8",
    )

    _, new1 = patch.apply_ops(
        f,
        [
            {
                "op": "upsert_def",
                "name": "g",
                "text": "def g():\n    return 2\n",
            },
            {
                "op": "upsert_class",
                "name": "B",
                "text": "class B:\n    pass\n",
            },
            {
                "op": "upsert_method",
                "class": "A",
                "name": "f",
                "text": "<<INDENT>>def f(self):\n<<INDENT>>    return 3\n",
            },
            {
                "op": "upsert_method",
                "class": "A",
                "name": "h",
                "text": "<<INDENT>>def h(self):\n<<INDENT>>    return 4\n",
            },
        ],
    )

    assert "def g():" in new1
    assert "class B:" in new1
    assert "return 3" in new1
    assert "def h(self):" in new1


def test_patch_main_errors_on_unknown_operation(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("hi\n", encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(
        '{"spec_version":1,"files":[{"path":"x.txt","ops":[{"op":"nope"}]}]}',
        encoding="utf-8",
    )

    old = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        rc = patch.main(["spec.json"])
        assert rc == 2
    finally:
        os.chdir(old)


def test_patch_helper_guards_and_limits(monkeypatch):
    import io

    monkeypatch.setattr(patch.sys, "stdin", io.StringIO('{"spec_version":1}'))
    data, size = patch._load_json("-")
    assert data["spec_version"] == 1
    assert size > 0

    with pytest.raises(patch.PatchSpecError):
        patch._compile_regex("(" * 5, "x")
    with pytest.raises(patch.PatchSpecError):
        patch._compile_regex("a" * (patch._MAX_PATTERN_LENGTH + 1), "x")

    rx = patch._compile_regex("a", "ok")
    with pytest.raises(patch.PatchSpecError):
        patch._find_matches(rx, "a" * 4, max_matches=1)


def test_patch_read_and_op_edge_paths(tmp_path: Path, monkeypatch):
    f = tmp_path / "f.txt"
    f.write_text("line\n", encoding="utf-8")

    # simulate symlink open rejection without relying on platform specifics
    err = OSError()
    err.errno = errno.ELOOP

    def _open(*_a, **_k):
        raise err

    monkeypatch.setattr(patch.os, "open", _open)
    with pytest.raises(patch.PatchSpecError):
        patch._read_text_raw(f)

    text = "A\r\nB\n"
    out = patch._op_insert_after(text, {"pattern": r"^A\r?$", "text": "X\n"})
    assert out.startswith("A\r\nX\n")

    no_change = patch._op_insert_before(
        "A\n", {"pattern": r"^A$", "text": "", "skip_if_contains": r"A"}
    )
    assert no_change == "A\n"


def test_patch_spec_validation_and_path_helpers(tmp_path: Path) -> None:
    with pytest.raises(patch.PatchSpecError):
        patch._normalize_rel_path("a\\b.txt")
    with pytest.raises(patch.PatchSpecError):
        patch._normalize_rel_path("../x")

    root = tmp_path / "r"
    root.mkdir()
    tgt = patch._resolve_target(root, "a/b.txt")
    assert tgt == root / "a" / "b.txt"

    assert patch._count_changed_bytes("a\n", "a\n") == 0
    assert patch._count_changed_bytes("a\n", "b\n") > 0

    op = patch._validate_op({"op": "insert_before", "pattern": "x", "text": "y"})
    assert op["op"] == "insert_before"
    with pytest.raises(patch.PatchSpecError):
        patch._validate_op({"pattern": "x"})
    with pytest.raises(patch.PatchSpecError):
        patch._validate_op({"op": "unknown"})

    files = patch._normalize_files(
        {
            "files": [
                {"path": "a.txt", "ops": [{"op": "insert_before", "pattern": "x", "text": "y"}]}
            ]
        }
    )
    assert files[0]["path"] == "a.txt"

    with pytest.raises(patch.PatchSpecError):
        patch._normalize_files({"files": "bad"})

    spec_files = patch._validate_spec(
        {
            "spec_version": 1,
            "files": [
                {"path": "a.txt", "ops": [{"op": "insert_before", "pattern": "x", "text": "y"}]}
            ],
        }
    )
    assert spec_files[0]["path"] == "a.txt"
    with pytest.raises(patch.PatchSpecError):
        patch._validate_spec({"spec_version": 2, "files": []})


def test_patch_write_report_force_and_overwrite(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    patch._write_report(str(report), {"ok": True}, force=False)
    assert report.exists()
    with pytest.raises(patch.PatchSpecError):
        patch._write_report(str(report), {"ok": True}, force=False)
    patch._write_report(str(report), {"ok": False}, force=True)
    assert "false" in report.read_text(encoding="utf-8").lower()


def test_patch_ast_error_and_decorator_paths() -> None:
    with pytest.raises(patch.PatchSpecError):
        patch._op_ensure_import("def x(:\n", {"name": "json"})

    src = "@d1\n@d2\ndef f():\n    return 1\n"
    out = patch._op_upsert_def(src, {"name": "f", "text": "def f():\n    return 2\n"})
    assert "return 2" in out

    csrc = "@dc\nclass A:\n    pass\n"
    cout = patch._op_upsert_class(csrc, {"name": "A", "text": "class A:\n    x = 1\n"})
    assert "x = 1" in cout


def test_patch_replace_or_insert_block_edge_and_method_decorator() -> None:
    txt = "start\na\nend\n"
    out = patch._op_replace_or_insert_block(
        txt,
        {"start": "^start$", "end": "^missing$", "insert_after": "^a$", "text": "X\n"},
    )
    assert "a\nX\nend" in out

    code = "class C:\n    @dec\n    def m(self):\n        return 1\n"
    replaced = patch._op_upsert_method(
        code,
        {"class": "C", "name": "m", "text": "<<INDENT>>def m(self):\n<<INDENT>>    return 2\n"},
    )
    assert "return 2" in replaced


def test_patch_path_and_default_root_branches(tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(patch.PatchSpecError):
        patch._normalize_rel_path("a//b")

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    link = root / "link"
    link.symlink_to(outside)
    with pytest.raises(patch.PatchSpecError):
        patch._resolve_target(root, "link")

    def raise_oserror(*_a, **_k):
        raise OSError("boom")

    monkeypatch.setattr(patch.subprocess, "run", raise_oserror)
    assert patch._default_root() == Path.cwd()
