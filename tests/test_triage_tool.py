import importlib.util
import io
import os
from contextlib import redirect_stdout
from pathlib import Path


def _load_triage():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "triage.py"
    spec = importlib.util.spec_from_file_location("triage", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(mod, argv: list[str], cwd: Path) -> tuple[int, str]:
    old = Path.cwd()
    os.chdir(cwd)
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = int(mod.main(argv))
        return rc, buf.getvalue()
    finally:
        os.chdir(old)


def test_compile_mode_reports_syntax_error_context(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    bad = tmp_path / "src" / "bad.py"
    bad.write_text('def f():\n    x = "hi\n', encoding="utf-8")

    triage = _load_triage()
    rc, out = _run(
        triage,
        ["--path", str(tmp_path), "--mode", "compile", "--targets", "src", "--radius", "2"],
        tmp_path,
    )
    assert rc == 1
    assert "syntax-error" in out
    assert "bad.py" in out
    assert "def f()" in out


def test_compile_mode_reports_nul_bytes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    bad = tmp_path / "src" / "nul.py"
    bad.write_bytes(b"print('ok')\x00\n")

    triage = _load_triage()
    rc, out = _run(
        triage, ["--path", str(tmp_path), "--mode", "compile", "--targets", "src"], tmp_path
    )
    assert rc == 1
    assert "nul-bytes" in out

    rc2, out2 = _run(
        triage,
        ["--path", str(tmp_path), "--mode", "compile", "--targets", "src", "--fix-nul"],
        tmp_path,
    )
    assert rc2 == 0
    assert "compile ok" in out2
    assert b"\x00" not in bad.read_bytes()


def test_parse_pytest_log_prints_useful_commands(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    log.write_text(
        "\n".join(
            [
                "FAILED tests/test_x.py::test_a - AssertionError: nope",
                'File "tests/test_x.py", line 12, in test_a',
                "E   assert 1 == 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    triage = _load_triage()
    rc, out = _run(triage, ["--parse-pytest-log", str(log), "--radius", "3"], tmp_path)
    assert rc == 1
    assert "triage: failure summary" in out
    assert "pytest -q tests/test_x.py::test_a" in out
    assert "nl -ba tests/test_x.py | sed -n '9,15p'" in out


def test_parse_pytest_log_pass_only_returns_ok(tmp_path: Path) -> None:
    log = tmp_path / "pass.log"
    log.write_text("371 passed in 1.23s\n", encoding="utf-8")
    triage = _load_triage()
    rc, out = _run(triage, ["--parse-pytest-log", str(log)], tmp_path)
    assert rc == 0
    assert "no failures found in log" in out


def test_run_pytest_success_writes_tee(tmp_path: Path, monkeypatch) -> None:
    triage = _load_triage()

    class R:
        returncode = 0
        stdout = "3 passed in 0.01s\n"

    def fake_run(*a, **k):
        return R()

    monkeypatch.setattr(triage.subprocess, "run", fake_run)
    log = tmp_path / "pytest.log"
    rc, out = _run(
        triage, ["--path", str(tmp_path), "--mode", "pytest", "--run", "--tee", str(log)], tmp_path
    )
    assert rc == 0
    assert "pytest ok" in out
    assert log.read_text(encoding="utf-8") == R.stdout


def test_run_pytest_failure_prints_summary_and_commands(tmp_path: Path, monkeypatch) -> None:
    triage = _load_triage()

    class R:
        returncode = 1
        stdout = (
            "\n".join(
                [
                    "FAILED tests/test_x.py::test_a - AssertionError: nope",
                    'File "tests/test_x.py", line 12, in test_a',
                    "E   assert 1 == 2",
                ]
            )
            + "\n"
        )

    def fake_run(*a, **k):
        return R()

    monkeypatch.setattr(triage.subprocess, "run", fake_run)
    log = tmp_path / "pytest.log"
    rc, out = _run(
        triage,
        [
            "--path",
            str(tmp_path),
            "--mode",
            "pytest",
            "--run",
            "--tee",
            str(log),
            "--max-items",
            "10",
        ],
        tmp_path,
    )
    assert rc == 1
    assert "triage: failure summary" in out
    assert "pytest -q tests/test_x.py::test_a" in out
    assert log.read_text(encoding="utf-8") == R.stdout


def test_run_pytest_failure_emits_targeted_grep_hits(tmp_path: Path, monkeypatch) -> None:
    triage = _load_triage()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        "def test_a():\n    assert 1 == 2\n", encoding="utf-8"
    )
    (tmp_path / "src" / "x.py").write_text('VALUE = "nope"\n', encoding="utf-8")

    class R:
        returncode = 1
        stdout = (
            "FAILED tests/test_x.py::test_a - AssertionError: nope\n"
            'File "tests/test_x.py", line 2, in test_a\n'
            "E   assert 1 == 2\n"
        )

    def fake_run(*a, **k):
        return R()

    monkeypatch.setattr(triage.subprocess, "run", fake_run)
    log = tmp_path / "pytest.log"
    rc, out = _run(
        triage,
        [
            "--path",
            str(tmp_path),
            "--mode",
            "pytest",
            "--run",
            "--tee",
            str(log),
            "--grep",
            "--grep-term",
            "assert 1 == 2",
            "--grep-limit",
            "5",
            "--targets",
            "src",
            "tests",
            "--pytest-args",
            "-q",
        ],
        tmp_path,
    )
    assert rc == 1
    assert "triage: grep hits" in out
    assert "tests/test_x.py:2" in out


def test_parse_security_log_json_summarizes_findings(tmp_path: Path) -> None:
    log = tmp_path / "security.json"
    log.write_text(
        '{"findings":[{"rule_id":"SEC_OS_SYSTEM","severity":"error","path":"src/a.py","line":10,"message":"x"}]}'
        + "\n",
        encoding="utf-8",
    )

    triage = _load_triage()
    rc, out = _run(triage, ["--parse-security-log", str(log)], tmp_path)
    assert rc == 1
    assert "triage: security summary" in out
    assert "SEC_OS_SYSTEM" in out


def test_parse_security_log_text_summarizes_findings(tmp_path: Path) -> None:
    log = tmp_path / "security.txt"
    log.write_text(
        "security scan: total=1 error=0 warn=1 info=0\n"
        "top findings:\n"
        "- [warn] SEC_WEAK_HASH src/a.py:7 Weak hash usage\n",
        encoding="utf-8",
    )

    triage = _load_triage()
    rc, out = _run(triage, ["--parse-security-log", str(log)], tmp_path)
    assert rc == 1
    assert "triage: security summary" in out
    assert "SEC_WEAK_HASH" in out


def test_run_security_check_includes_baseline_flag(tmp_path: Path, monkeypatch) -> None:
    triage = _load_triage()
    captured: dict[str, object] = {}

    class R:
        returncode = 0
        stdout = '{"findings": []}\n'

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return R()

    monkeypatch.setattr(triage.subprocess, "run", fake_run)
    rc, _out = _run(
        triage,
        [
            "--mode",
            "security",
            "--run-security",
            "--security-baseline",
            "tools/security.baseline.json",
        ],
        tmp_path,
    )
    assert rc == 0
    cmd = captured.get("cmd")
    assert isinstance(cmd, list)
    assert "--baseline" in cmd


def test_run_security_with_baseline_uses_new_findings(tmp_path: Path, monkeypatch) -> None:
    triage = _load_triage()

    class R:
        returncode = 0
        stdout = (
            '{"findings":[{"rule_id":"SEC_WEAK_HASH","severity":"warn","path":"src/a.py","line":1,"message":"x"}],'
            '"new_findings":[]}\n'
        )

    monkeypatch.setattr(triage.subprocess, "run", lambda *a, **k: R())
    rc, out = _run(
        triage,
        [
            "--mode",
            "security",
            "--run-security",
            "--security-baseline",
            "tools/security.baseline.json",
        ],
        tmp_path,
    )
    assert rc == 0
    assert "no security findings" in out.lower()
