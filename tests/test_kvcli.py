import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_kvcli(
    *args: str,
    input_text: str | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
):
    import sys

    here = Path(__file__).resolve()
    if "mutants" in here.parts:
        i = here.parts.index("mutants")
        repo_root = Path(here.parts[0], *here.parts[1:i])
    else:
        repo_root = here.parent.parent

    env2 = os.environ.copy()
    if env:
        env2.update(env)

    want = str(repo_root / "src")
    existing = env2.get("PYTHONPATH", "")
    if existing:
        env2["PYTHONPATH"] = want + os.pathsep + existing
    else:
        env2["PYTHONPATH"] = want

    for k in list(env2):
        if k.startswith("MUTMUT_"):
            env2.pop(k, None)

    cmd = [sys.executable, "-m", "sdetkit.kvcli", *args]
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        env=env2,
        cwd=str(repo_root),
        timeout=timeout,
    )


def test_kvcli_text_ok():
    p = run_kvcli("--text", "a=1 b=two")
    assert p.returncode == 0
    assert p.stderr == ""
    assert json.loads(p.stdout) == {"a": "1", "b": "two"}


def test_kvcli_stdin_ok():
    p = run_kvcli(input_text="x=9 y=10\n")
    assert p.returncode == 0
    assert p.stderr == ""
    assert json.loads(p.stdout) == {"x": "9", "y": "10"}


def test_kvcli_path_ok(tmp_path):
    f = tmp_path / "in.txt"
    f.write_text("k=v\n", encoding="utf-8")
    p = run_kvcli("--path", str(f))
    assert p.returncode == 0
    assert p.stderr == ""
    assert json.loads(p.stdout) == {"k": "v"}


def test_kvcli_bad_input_exit_2():
    p = run_kvcli("--text", "a=1 b")
    assert p.returncode == 2
    assert p.stdout == ""
    assert p.stderr.strip() != ""
    assert "traceback" not in p.stderr.lower()


def test_kvcli_text_and_path_together_exit_2():
    p = run_kvcli("--text", "a=1", "--path", "whatever.txt")
    assert p.returncode == 2
    assert p.stdout == ""
    assert p.stderr.strip() != ""
    assert "traceback" not in p.stderr.lower()


def test_kvcli_path_missing_exit_2(tmp_path):
    missing = tmp_path / "missing.txt"
    p = run_kvcli("--path", str(missing))
    assert p.returncode == 2
    assert p.stdout == ""
    assert p.stderr.strip() != ""
    assert "traceback" not in p.stderr.lower()


def test_kvcli_multiline_ignores_bad_lines_and_merges_last_wins():
    p = run_kvcli(input_text="a=1\nbadline\nb=2 a=3\n")
    assert p.returncode == 0
    assert p.stderr == ""
    assert json.loads(p.stdout) == {"a": "3", "b": "2"}


def test_kvcli_stdout_is_single_json_line_with_newline():
    p = run_kvcli("--text", "a=1")
    assert p.returncode == 0
    assert p.stderr == ""
    assert p.stdout.endswith("\n")
    assert p.stdout.count("\n") == 1
    assert p.stdout.strip() == '{"a": "1"}'


def test_kvcli_json_key_order_is_deterministic():
    p = run_kvcli("--text", "b=2 a=1")
    assert p.returncode == 0
    assert p.stderr == ""
    assert p.stdout == '{"a": "1", "b": "2"}\n'


def test_kvcli_on_error_emits_no_stdout_even_newline():
    p = run_kvcli("--text", "a=1 b")
    assert p.returncode == 2
    assert p.stdout == ""
    assert p.stderr.strip() != ""


def test_kvcli_text_and_stdin_produce_identical_output():
    p1 = run_kvcli("--text", 'a="hello world" b=2')
    p2 = run_kvcli(input_text='a="hello world" b=2\n')
    assert p1.returncode == 0
    assert p2.returncode == 0
    assert p1.stderr == ""
    assert p2.stderr == ""
    assert p1.stdout == p2.stdout


def test_kvcli_supports_hash_comments_in_input():
    p = run_kvcli(input_text="# leading comment\na=1 b=2 # trailing\n")
    assert p.returncode == 0
    assert p.stderr == ""
    assert json.loads(p.stdout) == {"a": "1", "b": "2"}


def test_kvcli_strict_rejects_any_invalid_line():
    p = run_kvcli("--strict", input_text="a=1\nbadline\n")
    assert p.returncode == 2
    assert p.stdout == ""
    assert p.stderr.strip() != ""


def test_kvcli_strict_accepts_comments_and_valid_lines_only():
    p = run_kvcli("--strict", input_text="# comment\na=1\nb=2 # trailing\n")
    assert p.returncode == 0
    assert p.stderr == ""
    assert json.loads(p.stdout) == {"a": "1", "b": "2"}


def test_kvcli_strict_error_mentions_line_number_for_invalid_line():
    p = run_kvcli("--strict", input_text="ok=1\nnotkv\n")
    assert p.returncode == 2
    assert "line 2" in p.stderr.lower()


def test_build_comment_aware_parser_supports_legacy_parser_signature():
    import sdetkit.kvcli as kvcli

    parser = kvcli._build_comment_aware_parser(lambda line: {"line": line})
    assert parser("x") == {"line": "x"}


def test_build_comment_aware_parser_enables_comments_for_modern_parser():
    import sdetkit.kvcli as kvcli

    parser = kvcli._build_comment_aware_parser(kvcli.parse_kv_line)
    assert parser("a=1 # trailing") == {"a": "1"}


def test_kvcli_runner_supports_timeout(tmp_path):
    p = run_kvcli("--text", "a=1", timeout=0.2)
    assert p.returncode == 0


def test_kvcli_main_text_ok(capsys):
    rc = __import__("sdetkit.kvcli", fromlist=["main"]).main(["--text", "a=1 b=two"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert json.loads(out.out) == {"a": "1", "b": "two"}


def test_kvcli_main_path_ok(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("k=v\n", encoding="utf-8")
    rc = __import__("sdetkit.kvcli", fromlist=["main"]).main(["--path", str(f)])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert json.loads(out.out) == {"k": "v"}


def test_kvcli_main_stdin_ok(monkeypatch, capsys):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("x=9 y=10\n"))
    rc = __import__("sdetkit.kvcli", fromlist=["main"]).main([])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""
    assert json.loads(out.out) == {"x": "9", "y": "10"}


def test_kvcli_main_text_and_path_is_error(capsys):
    kv = __import__("sdetkit.kvcli", fromlist=["main"])
    with pytest.raises(SystemExit) as ei:
        kv.main(["--text", "a=1", "--path", "x.txt"])
    out = capsys.readouterr()
    assert ei.value.code == 2
    assert out.out == ""
    assert out.err.strip() != ""


def test_kvcli_main_path_cannot_read_is_error(tmp_path, capsys):
    kv = __import__("sdetkit.kvcli", fromlist=["main"])
    missing = tmp_path / "nope.txt"
    with pytest.raises(SystemExit) as ei:
        kv.main(["--path", str(missing)])
    out = capsys.readouterr()
    assert ei.value.code == 2
    assert out.out == ""
    assert out.err.strip() != ""


def test_kvcli_main_invalid_input_exits_2(monkeypatch, capsys):
    import io

    kv = __import__("sdetkit.kvcli", fromlist=["main"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("badline\nstillbad\n"))
    with pytest.raises(SystemExit) as ei:
        kv.main([])
    out = capsys.readouterr()
    assert ei.value.code == 2
    assert out.out == ""
    assert out.err.strip() != ""


def test_kvcli_main_inprocess_ignores_bad_lines_and_keeps_last_wins(monkeypatch, capsys):
    import io
    import sys as _sys

    import sdetkit.kvcli as kvcli

    monkeypatch.setattr(_sys, "stdin", io.StringIO("badline\na=1\nb=2 a=3\n"))
    rc = kvcli.main([])
    assert rc == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert json.loads(out) == {"a": "3", "b": "2"}


def test_kvcli_run_as_module_hits___main__(monkeypatch, capsys):
    import runpy
    import sys as _sys

    _sys.modules.pop("sdetkit.kvcli", None)

    monkeypatch.setattr(_sys, "argv", ["sdetkit.kvcli", "--text", "a=1"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_module("sdetkit.kvcli", run_name="__main__")
    assert ei.value.code == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert json.loads(out) == {"a": "1"}


def test_kvcli_main_hits_continue_branch(monkeypatch, capsys):
    import io
    import sys as _sys

    import sdetkit.kvcli as kvcli

    monkeypatch.setattr(_sys, "stdin", io.StringIO("badline\n\nk=v\n"))
    rc = kvcli.main([])
    assert rc == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert json.loads(out) == {"k": "v"}
