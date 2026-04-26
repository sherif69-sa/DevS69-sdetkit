import importlib
import runpy
import sys

import pytest


def _exit_code(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return 1


def _run_cli(argv: list[str]) -> int:
    mod = importlib.import_module("sdetkit.cli")
    main = mod.main
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sdetkit", *argv]
        try:
            main()
        except SystemExit as exc:
            return _exit_code(exc.code)
        return 0
    finally:
        sys.argv = old_argv


def _run_entrypoint(fn_name: str, argv0: str, argv: list[str]) -> int:
    mod = importlib.import_module("sdetkit.entrypoints")
    fn = getattr(mod, fn_name)
    old_argv = sys.argv[:]
    try:
        sys.argv = [argv0, *argv]
        with pytest.raises(SystemExit) as excinfo:
            fn()
        return _exit_code(excinfo.value.code)
    finally:
        sys.argv = old_argv


def test_kvcli_entrypoint_help_executes_wrapper(capsys) -> None:
    assert _run_entrypoint("kvcli", "kvcli", ["--help"]) == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()


def test_apigetcli_entrypoint_help_executes_wrapper(capsys) -> None:
    assert _run_entrypoint("apigetcli", "apigetcli", ["--help"]) == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()


def test_cli_help_smoke(capsys) -> None:
    assert _run_cli(["--help"]) == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()


def test_cli_unknown_command_smoke(capsys) -> None:
    code = _run_cli(["__definitely_not_a_command__"])
    captured = capsys.readouterr()
    assert code != 0
    assert "invalid choice" in captured.err.lower() or "usage:" in captured.err.lower()


def test_cli_module_main_guard_smoke() -> None:
    old_argv = sys.argv[:]
    try:
        sys.modules.pop("sdetkit.cli", None)
        sys.argv = ["sdetkit", "--help"]
        try:
            runpy.run_module("sdetkit.cli", run_name="main_")
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
