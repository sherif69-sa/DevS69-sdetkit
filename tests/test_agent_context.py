from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_execution_plan import (
    AGENT_CONTEXT_SCHEMA_VERSION,
    _estimate_tokens,
    _find_enclosing_ast_symbol,
    _parse_failure_frame,
    _slice_source_snippet,
    context_main,
    main,
    render_agent_context_markdown,
    slice_agent_context,
)


def test_estimate_tokens() -> None:
    assert _estimate_tokens("") == 1
    assert _estimate_tokens("a" * 100) > 10


def test_find_enclosing_ast_symbol() -> None:
    code = (
        "class Worker:\n"
        "    def run(self):\n"
        "        x = 1\n"
        "        assert x == 2\n"
        "def helper():\n"
        "    return 42\n"
    )
    tree = ast.parse(code)
    # Line 4 is 'assert x == 2' inside 'run'
    match = _find_enclosing_ast_symbol(tree, 4)
    assert match is not None
    sym, start, end = match
    assert sym == "run"
    assert start == 2
    assert end == 4

    # Line 6 is 'return 42' inside 'helper'
    match_helper = _find_enclosing_ast_symbol(tree, 6)
    assert match_helper is not None
    assert match_helper[0] == "helper"

    # Line 99 is outside
    assert _find_enclosing_ast_symbol(tree, 99) is None


def test_slice_source_snippet(tmp_path: Path) -> None:
    non_existent = tmp_path / "ghost.py"
    snippet, sym, _, _ = _slice_source_snippet(non_existent, 10)
    assert snippet == ""
    assert sym == "<unknown>"

    py_file = tmp_path / "sample.py"
    py_file.write_text(
        "def compute(n):\n    step1 = n * 2\n    assert step1 == 10\n    return step1\n",
        encoding="utf-8",
    )
    snippet, sym, start, end = _slice_source_snippet(py_file, 3)
    assert sym == "compute"
    assert start == 1
    assert end == 4
    assert ">>    3 |     assert step1 == 10" in snippet
    assert "      1 | def compute(n):" in snippet


def test_parse_failure_frame(tmp_path: Path) -> None:
    demo_file = tmp_path / "tests" / "test_math.py"
    demo_file.parent.mkdir(parents=True)
    demo_file.write_text("def test_fail(): assert False\n", encoding="utf-8")

    log = (
        "Traceback (most recent call last):\n"
        '  File "/site-packages/pytest.py", line 100, in run\n'
        f'  File "{demo_file}", line 1, in test_fail\n'
        "    assert False\n"
        "AssertionError: assert False\n"
        "E   assert False\n"
    )

    f_rel, line_no, fn, err, diff = _parse_failure_frame(log, tmp_path)
    assert "test_math.py" in f_rel
    assert line_no == 1
    assert "AssertionError" in err
    assert "assert False" in diff


def test_slice_agent_context(tmp_path: Path) -> None:
    src_file = tmp_path / "test_example.py"
    src_file.write_text(
        "def test_division():\n"
        "    num = 100\n"
        "    denom = 0\n"
        "    result = num / denom\n"
        "    assert result == 0\n",
        encoding="utf-8",
    )

    log = (
        "FAILED test_example.py::test_division - ZeroDivisionError: division by zero\n"
        "test_example.py:4: in test_division\n"
        "    result = num / denom\n"
        "E   ZeroDivisionError: division by zero\n"
    )

    report = slice_agent_context(log, root=tmp_path, max_tokens=1000)
    assert report["schema_version"] == AGENT_CONTEXT_SCHEMA_VERSION
    assert report["target_file"] == "test_example.py"
    assert report["line_number"] == 4
    assert report["enclosing_symbol"] == "test_division"
    assert "ZeroDivisionError" in report["error_message"]
    assert report["token_metrics"]["raw_log_tokens"] > 0
    assert report["token_metrics"]["sliced_context_tokens"] > 0

    md = render_agent_context_markdown(report)
    assert "# SDETKit Sliced Agent Context" in md
    assert "Target:" in md
    assert "### Sliced AST Context" in md


def test_context_main_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_file = tmp_path / "ci_fail.log"
    log_file.write_text(
        "FAILED tests/test_unit.py:10: in test_check\nAssertionError: assert 1 == 2\nE assert 1 == 2\n",
        encoding="utf-8",
    )
    json_out = tmp_path / "context.json"
    summary_out = tmp_path / "prompt.md"

    rc = context_main(
        [
            str(log_file),
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
        ]
    )
    assert rc == 0
    assert json_out.is_file()
    assert summary_out.is_file()
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == AGENT_CONTEXT_SCHEMA_VERSION
    assert payload["line_number"] == 10


def test_main_dispatch_context(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_file = tmp_path / "fail.log"
    log_file.write_text("tests/test_x.py:5: AssertionError\n", encoding="utf-8")

    rc = main(["context", str(log_file), "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == AGENT_CONTEXT_SCHEMA_VERSION
