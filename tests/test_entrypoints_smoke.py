import importlib
import inspect
import sys

import pytest


def test_entrypoints_module_imports() -> None:
    importlib.import_module("sdetkit._entrypoints")


def test_main_module_help_does_not_crash() -> None:
    old_argv = sys.argv[:]
    try:
        sys.modules.pop("sdetkit.__main__", None)
        sys.argv = ["sdetkit", "--help"]
        with pytest.raises(SystemExit):
            importlib.import_module("sdetkit.__main__")
    finally:
        sys.argv = old_argv


def test_entrypoints_runner_smoke() -> None:
    mod = importlib.import_module("sdetkit._entrypoints")
    fn = getattr(mod, "main", None) or getattr(mod, "run", None) or getattr(mod, "cli", None)
    if fn is None or not callable(fn):
        pytest.skip("no callable entrypoint runner found")

    sig = inspect.signature(fn)
    if len(sig.parameters) == 0:
        args: list[object] = []
    elif len(sig.parameters) == 1:
        args = [["--help"]]
    else:
        pytest.skip("entrypoint runner signature not supported")

    try:
        fn(*args)
    except SystemExit:
        pass
