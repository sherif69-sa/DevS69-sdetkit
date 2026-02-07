import importlib
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
