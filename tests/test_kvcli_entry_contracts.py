from __future__ import annotations

import io
import json

import pytest

from sdetkit import kvcli


@pytest.mark.parametrize(
    "entry", [kvcli.main, kvcli.cli_entry], ids=["argparse", "fast"]
)
@pytest.mark.parametrize("policy,expected", [("last", "2"), ("first", "1")])
def test_entrypoints_agree_on_comments_and_duplicate_policies(
    entry, policy, expected, capsys
):
    assert (
        entry(["--text", 'a=1\na=2\nb="two words" # ignored', "--duplicates", policy])
        == 0
    )
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == {"a": expected, "b": "two words"}
    assert output.out.endswith("\n")


@pytest.mark.parametrize("entry", [kvcli.main, kvcli.cli_entry])
def test_duplicate_error_reports_actual_later_line(entry, capsys):
    with pytest.raises(SystemExit) as error:
        entry(["--text", "a=1\nb=2\na=3", "--duplicates", "error"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "duplicate key: a at line 3\n"


@pytest.mark.parametrize("entry", [kvcli.main, kvcli.cli_entry])
@pytest.mark.parametrize("strict", [False, True])
def test_invalid_line_skipping_vs_strict_failure(entry, strict, capsys):
    args = ["--text", "a=1\ninvalid\nb=2"]
    if strict:
        args.append("--strict")
        with pytest.raises(SystemExit) as error:
            entry(args)
        assert error.value.code == 2
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err == "invalid input at line 2\n"
    else:
        assert entry(args) == 0
        output = capsys.readouterr()
        assert output.err == ""
        assert json.loads(output.out) == {"a": "1", "b": "2"}


@pytest.mark.parametrize("flag", ["--text", "--path", "--duplicates"])
@pytest.mark.parametrize(
    "following", [None, "--strict", "--help", "--path", "--text", "--duplicates"]
)
def test_fast_parser_missing_values_fail_as_usage_errors(flag, following, capsys):
    args = [flag] if following is None else [flag, following]
    with pytest.raises(SystemExit) as error:
        kvcli.cli_entry(args)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "usage: kvcli" in output.err
    assert f"argument {flag}: expected one argument\n" in output.err


@pytest.mark.parametrize("args", [["--unknown"], ["--duplicates", "invalid"]])
def test_fast_parser_rejects_unknown_options_and_policy(args, capsys):
    with pytest.raises(SystemExit) as error:
        kvcli.cli_entry(args)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "usage: kvcli" in output.err


def test_fast_entry_uses_sys_argv_and_stdin(monkeypatch, capsys):
    monkeypatch.setattr(kvcli.sys, "argv", ["kvcli", "--duplicates", "first"])
    monkeypatch.setattr(kvcli.sys, "stdin", io.StringIO("a=1\na=2"))
    assert kvcli.cli_entry() == 0
    assert capsys.readouterr().out == '{"a": "1"}\n'


def test_adapter_supports_kwargs_and_plain_callable_without_dropping_options():
    calls = []

    def flexible(line, **kwargs):
        calls.append((line, kwargs))
        return {"x": line}

    assert kvcli._build_comment_aware_parser(flexible, duplicate_policy="error")(
        "ok"
    ) == {"x": "ok"}
    assert calls == [("ok", {"allow_comments": True, "duplicate_policy": "error"})]

    def plain(line):
        return {"x": line}

    assert kvcli._build_comment_aware_parser(plain)("ok") == {"x": "ok"}


def test_adapter_passes_only_supported_keyword():
    def comments_only(line, *, allow_comments=False):
        assert allow_comments is True
        return {"x": line}

    def duplicates_only(line, *, duplicate_policy="last"):
        assert duplicate_policy == "first"
        return {"x": line}

    assert kvcli._build_comment_aware_parser(comments_only)("ok") == {"x": "ok"}
    assert kvcli._build_comment_aware_parser(duplicates_only, duplicate_policy="first")(
        "ok"
    ) == {"x": "ok"}
