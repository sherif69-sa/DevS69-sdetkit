import importlib.util
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path


def _load_triage():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "triage.py"
    spec = importlib.util.spec_from_file_location("triage", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["triage"] = mod
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
    assert "syntax" in out
    assert "src/bad.py" in out
    assert "def f():" in out


def test_compile_mode_reports_nul_bytes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    bad = tmp_path / "src" / "nul.py"
    bad.write_bytes(b"print('ok')\x00\n")

    triage = _load_triage()
    rc, out = _run(
        triage, ["--path", str(tmp_path), "--mode", "compile", "--targets", "src"], tmp_path
    )

    assert rc == 1
    assert "nul" in out.lower()
    assert "src/nul.py" in out


def test_parse_pytest_log_prints_useful_commands(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    log.write_text(
        "\n".join(
            [
                "FAILED tests/test_x.py::test_a - AssertionError: nope",
                'File "/tmp/tests/test_x.py", line 12, in test_a',
                "E   assert 1 == 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    triage = _load_triage()
    rc, out = _run(triage, ["--parse-pytest-log", str(log), "--radius", "3"], tmp_path)

    assert rc == 0
    assert "pytest -q tests/test_x.py::test_a" in out
    assert "nl -ba" in out
    assert "sed -n" in out
