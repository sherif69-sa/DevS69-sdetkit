import json
import os
import sys
from pathlib import Path
import subprocess


def run_kvcli(*args, input_text=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    cmd = [sys.executable, "-m", "sdetkit.kvcli", *args]
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
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
