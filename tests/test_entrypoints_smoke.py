import importlib
import runpy
import sys

import pytest


def _run_cli(argv: list[str]) -> None:
    mod = importlib.import_module("sdetkit.cli")
    main = mod.main
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sdetkit", *argv]
        try:
            main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv


def _run_entrypoint(fn_name: str, argv0: str, argv: list[str]) -> None:
    mod = importlib.import_module("sdetkit.entrypoints")
    fn = getattr(mod, fn_name)
    old_argv = sys.argv[:]
    try:
        sys.argv = [argv0, *argv]
        with pytest.raises(SystemExit):
            fn()
    finally:
        sys.argv = old_argv


def test_kvcli_entrypoint_help_executes_wrapper() -> None:
    _run_entrypoint("kvcli", "kvcli", ["--help"])


def test_apigetcli_entrypoint_help_executes_wrapper() -> None:
    _run_entrypoint("apigetcli", "apigetcli", ["--help"])


def test_cli_help_smoke() -> None:
    _run_cli(["--help"])


def test_cli_unknown_command_smoke() -> None:
    _run_cli(["__definitely_not_a_command__"])


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
