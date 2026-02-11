from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit import patch


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
        '{"files":[{"path":"x.txt","ops":[{"op":"nope"}]}]}',
        encoding="utf-8",
    )

    old = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        with pytest.raises(SystemExit):
            patch.main(["spec.json"])
    finally:
        os.chdir(old)
