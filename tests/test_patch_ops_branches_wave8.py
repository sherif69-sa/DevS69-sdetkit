from __future__ import annotations

from pathlib import Path

import pytest

import sdetkit.patch as p
from sdetkit.patch import PatchSpecError


def test_write_atomic_rejects_symlink_target(tmp_path: Path) -> None:
    real = tmp_path / "real.txt"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    with pytest.raises(PatchSpecError, match="symlink target rejected"):
        p._write_atomic(link, "y")

    assert real.read_text(encoding="utf-8") == "x"


def test_write_atomic_rejects_symlink_during_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "t.txt"
    target.write_text("old", encoding="utf-8")

    calls = {"n": 0}

    def islink_toggle(_path: object) -> bool:
        calls["n"] += 1
        return calls["n"] >= 2

    monkeypatch.setattr(p.os.path, "islink", islink_toggle)

    with pytest.raises(PatchSpecError, match="symlink target rejected during write"):
        p._write_atomic(target, "new")

    assert target.read_text(encoding="utf-8") == "old"


def test_one_match_raises_on_zero_and_many() -> None:
    rx = p.re.compile(r"(?m)^x$")

    with pytest.raises(PatchSpecError, match="expected 1 match, got 0"):
        p._one_match(rx, "y\n", "lbl")

    with pytest.raises(PatchSpecError, match="expected 1 match, got 2"):
        p._one_match(rx, "x\nx\n", "lbl")


def test_op_insert_before_is_idempotent() -> None:
    text = "alpha\nbeta\n"
    op = {"pattern": r"(?m)^beta$", "text": "INS\n"}
    out1 = p._op_insert_before(text, op)
    out2 = p._op_insert_before(out1, op)
    assert out2 == out1


def test_op_insert_after_handles_crlf_and_lf() -> None:
    text_crlf = "a\r\nb\r\n"
    op = {"pattern": r"(?m)^a\r?$", "text": "INS\n"}
    out = p._op_insert_after(text_crlf, op)
    assert out.startswith("a\r\nINS\r\n") or out.startswith("a\r\nINS\n")

    text_lf = "a\nb\n"
    out2 = p._op_insert_after(text_lf, op)
    assert out2.startswith("a\nINS\n")


def test_ops_skip_via_should_skip_returns_text_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(p, "_should_skip", lambda _t, _o: True)
    s = "x\n"
    assert p._op_insert_after(s, {"pattern": "x", "text": "y"}) == s
    assert p._op_replace_once(s, {"pattern": "x", "text": "y"}) == s
    assert p._op_replace_block(s, {"start": "x", "end": "x", "text": "y"}) == s
    assert (
        p._op_replace_or_insert_block(
            s, {"start": "x", "end": "x", "text": "y", "insert_after": "x"}
        )
        == s
    )
    assert p._op_ensure_import(s, {"name": "os"}) == s


def test_replace_block_raises_when_end_not_found() -> None:
    text = "start\nmid\n"
    op = {"start": r"(?m)^start$", "end": r"(?m)^end$", "text": "X\n"}
    with pytest.raises(PatchSpecError, match="replace_block.end: no match after start"):
        p._op_replace_block(text, op)


def test_replace_or_insert_block_multiple_starts_raises() -> None:
    text = "S\nS\nE\n"
    op = {"start": r"(?m)^S$", "end": r"(?m)^E$", "text": "X\n", "insert_after": "S"}
    with pytest.raises(PatchSpecError, match="expected <= 1 match"):
        p._op_replace_or_insert_block(text, op)


def test_replace_or_insert_block_replaces_when_found_and_include_end_controls_cut() -> None:
    text = "AA\n  START\n  keep\n  END\nZZ\n"
    op1 = {"start": r"(?m)^  START$", "end": r"(?m)^  END$", "text": "NEW\n", "include_end": False}
    out1 = p._op_replace_or_insert_block(text, op1)
    assert "NEW\n" in out1
    assert "END\n" in out1

    op2 = {"start": r"(?m)^  START$", "end": r"(?m)^  END$", "text": "NEW\n", "include_end": True}
    out2 = p._op_replace_or_insert_block(text, op2)
    assert "NEW\n" in out2
    assert "END\n" not in out2


def test_replace_or_insert_block_requires_insert_after_when_not_found() -> None:
    text = "a\nb\n"
    op = {"start": r"(?m)^S$", "end": r"(?m)^E$", "text": "X\n"}
    with pytest.raises(PatchSpecError, match="insert_after: required when block not found"):
        p._op_replace_or_insert_block(text, op)


def test_ensure_import_validates_name_and_inserts_after_docstring_and_imports() -> None:
    text = '"""doc"""\nimport sys\n\nx = 1\n'
    with pytest.raises(PatchSpecError, match="ensure_import.name: empty"):
        p._op_ensure_import(text, {"name": "  "})

    out = p._op_ensure_import(text.rstrip("\n"), {"name": "os"})
    assert "import os\n" in out
    assert out.startswith('"""doc"""')
    assert out.count("\n") >= text.count("\n")
