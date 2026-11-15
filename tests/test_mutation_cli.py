"""Tests for `sdetkit verify mutation` CLI."""

from __future__ import annotations

import json
from pathlib import Path

from sdetkit import mutation_cli


def test_discover_source_files_handles_file_and_dir(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    f1 = src / "a.py"
    f1.write_text("x = 1\n", encoding="utf-8")
    f2 = src / "b.txt"
    f2.write_text("hello\n", encoding="utf-8")

    assert mutation_cli._discover_source_files(f1) == [f1]
    assert mutation_cli._discover_source_files(f2) == []
    assert mutation_cli._discover_source_files(src) == [f1]


def test_render_markdown_handles_clean_and_surviving() -> None:
    not_run = mutation_cli.render_markdown({"ran": False, "reason": "no files"})
    assert "NOT RUN" in not_run
    assert "no files" in not_run

    clean = mutation_cli.render_markdown(
        {
            "ran": True,
            "score": 100.0,
            "killed": 3,
            "total": 3,
            "survived": 0,
            "minimum": 80.0,
            "ok": True,
            "survivors": [],
        }
    )
    assert "100.0% (3/3 killed)" in clean
    assert "All tested mutants were killed" in clean

    surviving = mutation_cli.render_markdown(
        {
            "ran": True,
            "score": 50.0,
            "killed": 1,
            "total": 2,
            "survived": 1,
            "minimum": 80.0,
            "ok": False,
            "survivors": [
                {
                    "path": "src/calc.py",
                    "line": 10,
                    "before": "if x > 0:",
                    "after": "if x >= 0:",
                    "hint": "test boundary",
                }
            ],
        }
    )
    assert "50.0% (1/2 killed)" in surviving
    assert "src/calc.py:10" in surviving
    assert "test boundary" in surviving


def test_run_targeted_mutation_on_code(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    if a > 0:\n        return a + b\n    return 0\n",
        encoding="utf-8",
    )
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(5, 5) == 10\n",
        encoding="utf-8",
    )

    payload = mutation_cli.run_targeted_mutation(
        root=tmp_path,
        target_path=tmp_path / "calc.py",
        pytest_args=[str(tmp_path / "test_calc.py")],
        max_mutants=10,
        min_score=0.0,
    )

    assert payload["ran"] is True
    assert payload["total"] > 0
    assert payload["killed"] >= 1
    assert payload["survived"] >= 1
    assert len(payload["survivors"]) == payload["survived"]


def test_mutation_cli_main_with_json_out(tmp_path: Path, capsys) -> None:
    (tmp_path / "calc.py").write_text("def inc(x):\n    return x + 1\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from calc import inc\n\ndef test_inc():\n    assert inc(1) == 2\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"

    rc = mutation_cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--path",
            "calc.py",
            "--out",
            str(out_json),
            "--format",
            "json",
            "--",
            str(tmp_path / "test_calc.py"),
        ]
    )

    assert rc == 0
    assert out_json.is_file()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["ran"] is True
    assert data["total"] > 0
