import argparse
import pathlib
import pytest
import sdetkit.kvcli as kvcli


def test_die_preserves_leading_whitespace_and_single_newline(capsys):
    with pytest.raises(SystemExit) as exc:
        kvcli._die("  hi  ")
    assert exc.value.code == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "  hi\n"


def test_main_help_has_prog_kvcli_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.splitlines()[0].startswith("usage: kvcli")
    assert "--text" in out.out
    assert "--path" in out.out


def test_main_argument_parser_passes_prog_and_add_help_explicit(monkeypatch):
    calls = []
    orig = argparse.ArgumentParser.__init__

    def wrapped(self, *args, **kwargs):
        calls.append(kwargs.copy())
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(argparse.ArgumentParser, "__init__", wrapped)

    rc = kvcli.main(["--text", "a=1"])
    assert rc == 0

    hits = [
        kw
        for kw in calls
        if kw.get("prog") == "kvcli" and ("add_help" in kw and kw["add_help"] is True)
    ]
    assert hits


def test_main_rejects_text_and_path_together(capsys, tmp_path):
    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--text", "a=1", "--path", str(tmp_path / "x.txt")])
    assert exc.value.code == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "use only one of --text or --path\n"


def test_main_cannot_read_file_message(capsys, tmp_path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--path", str(missing)])
    assert exc.value.code == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "cannot read file\n"


def test_main_path_read_text_passes_utf8_encoding(tmp_path, monkeypatch):
    f = tmp_path / "in.txt"
    f.write_bytes(b"b=2\na=1\n")

    calls = []
    orig = pathlib.Path.read_text

    def wrapped(self, *args, **kwargs):
        calls.append((args, kwargs.copy()))
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", wrapped)

    rc = kvcli.main(["--path", str(f)])
    assert rc == 0

    encs = [kw.get("encoding", None) for _a, kw in calls if "encoding" in kw]
    assert encs
    assert all(e == "utf-8" for e in encs)


def test_main_parse_kv_line_receives_no_line_endings(capsys, monkeypatch):
    def strict(line: str):
        assert not line.endswith("\n")
        assert not line.endswith("\r")
        return {}

    monkeypatch.setattr(kvcli, "parse_kv_line", strict)

    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--text", "a=1\n"])
    assert exc.value.code == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "invalid input\n"


def test_main_invalid_input_uses_strip_not_equal_empty_guard(capsys, monkeypatch):
    monkeypatch.setattr(kvcli, "parse_kv_line", lambda _line: {})
    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--text", "XXXX"])
    assert exc.value.code == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "invalid input\n"


def test_main_outputs_sorted_json_and_newline(capsys):
    rc = kvcli.main(["--text", "b=2\na=1\n"])
    assert rc == 0
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.endswith("\n")
    assert out.out.index('"a"') < out.out.index('"b"')


def test_main_add_argument_sets_default_none_for_text_and_path(monkeypatch):
    calls = []
    orig = argparse.ArgumentParser.add_argument

    def wrapped(self, *args, **kwargs):
        if args and args[0] in ("--text", "--path"):
            calls.append((args, kwargs.copy()))
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(argparse.ArgumentParser, "add_argument", wrapped)

    rc = kvcli.main(["--text", "a=1"])
    assert rc == 0

    seen = {args[0]: kw for args, kw in calls}
    assert "--text" in seen and "--path" in seen
    assert "default" in seen["--text"] and seen["--text"]["default"] is None
    assert "default" in seen["--path"] and seen["--path"]["default"] is None

def test_main_reads_from_stdin_when_no_text_or_path(monkeypatch, capsys):
    import io
    import json

    monkeypatch.setattr(kvcli.sys, "stdin", io.StringIO("b=2\na=1\n"))
    rc = kvcli.main([])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.endswith("\n")

    data = json.loads(out.out)
    assert data == {"a": "1", "b": "2"}
    assert out.out.index('"a"') < out.out.index('"b"')


def test_main_whitespace_only_stdin_outputs_empty_json(monkeypatch, capsys):
    import io

    monkeypatch.setattr(kvcli.sys, "stdin", io.StringIO(" \n\t\n"))
    rc = kvcli.main([])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out == "{}\n"


def test_main_invalid_stdin_dies(monkeypatch, capsys):
    import io

    monkeypatch.setattr(kvcli.sys, "stdin", io.StringIO("XXXX\n"))
    with pytest.raises(SystemExit) as exc:
        kvcli.main([])
    assert exc.value.code == 2

    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "invalid input\n"

def test_main_help_mentions_prog_and_options(capsys):
    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--help"])
    assert exc.value.code == 0

    out = capsys.readouterr()
    assert out.err == ""

    txt = out.out.lower()
    assert "usage:" in txt
    assert "kvcli" in txt
    assert "--text" in txt
    assert "--path" in txt


def test_main_unknown_arg_mentions_prog_and_arg(capsys):
    with pytest.raises(SystemExit) as exc:
        kvcli.main(["--nope"])
    assert exc.value.code == 2

    out = capsys.readouterr()
    assert out.out == ""

    err = out.err.lower()
    assert "usage:" in err
    assert "kvcli" in err
    assert "--nope" in out.err

def test_main_text_success_prints_and_returns_zero(capsys):
    rc = kvcli.main(["--text", "a=1\n"])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out != ""
    assert "a" in out.out
    assert "1" in out.out


def test_main_path_success_prints_and_returns_zero(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("a=1\n", encoding="utf-8")

    rc = kvcli.main(["--path", str(f)])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out != ""
    assert "a" in out.out
    assert "1" in out.out

def test_main_text_success_output_exact(capsys):
    rc = kvcli.main(["--text", "a=1\n"])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out == '{"a": "1"}\n'

def test_main_path_success_output_exact(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("a=1\n", encoding="utf-8")

    rc = kvcli.main(["--path", str(f)])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out == '{"a": "1"}\n'

def test_main_help_mentions_prog(capsys):
    import pytest

    with pytest.raises(SystemExit) as e:
        kvcli.main(["--help"])
    assert e.value.code == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert "kvcli" in out.out

def test_main_text_json_format_is_default(capsys):
    rc = kvcli.main(["--text", "b=2\na=1\n"])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.endswith("\n")
    assert out.out.count("\n") == 1

    s = out.out[:-1]
    import json
    obj = json.loads(s)
    assert obj == {"b": "2", "a": "1"}
    assert json.dumps(obj) == s
    assert json.dumps(obj, sort_keys=True) == s


def test_main_help_includes_prog_and_options(capsys):
    def call(argv):
        try:
            return kvcli.main(argv)
        except SystemExit as e:
            code = getattr(e, "code", 1)
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            return 1

    rc = call(["--help"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert out.out.startswith("usage: kvcli")
    assert "--text" in out.out
    assert "--path" in out.out
    assert "--help" in out.out


def test_main_unknown_option_mentions_prog_and_usage(capsys):
    def call(argv):
        try:
            return kvcli.main(argv)
        except SystemExit as e:
            code = getattr(e, "code", 1)
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            return 1

    rc = call(["--nope"])
    out = capsys.readouterr()
    assert rc == 2
    assert out.out == ""
    assert "usage:" in out.err.lower()
    assert "kvcli" in out.err


def test_main_text_whitespace_only_outputs_empty_json(capsys):
    def call(argv):
        try:
            return kvcli.main(argv)
        except SystemExit as e:
            code = getattr(e, "code", 1)
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            return 1

    rc = call(["--text", "  \n\t\n"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert out.out == "{}\n"

def test_main_text_blank_lines_output_empty_json(capsys):
    rc = kvcli.main(["--text", "\n\n"])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.endswith("\n")
    assert out.out.count("\n") == 1

    import json
    line = out.out[:-1]
    obj = json.loads(line)
    assert obj == {}
    assert json.dumps(obj) == line


def test_main_text_whitespace_only_output_empty_json(capsys):
    rc = kvcli.main(["--text", "  \t\n\n"])
    assert rc == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.endswith("\n")
    assert out.out.count("\n") == 1

    import json
    line = out.out[:-1]
    obj = json.loads(line)
    assert obj == {}
    assert json.dumps(obj) == line

def test_main_text_nonempty_with_no_pairs_is_error(capsys):
    try:
        rc = kvcli.main(["--text", "not_a_pair\nstill_not_a_pair\n"])
    except SystemExit as e:
        rc = e.code

    assert rc == 2

    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.endswith("\n")
    assert out.err.strip() != ""
