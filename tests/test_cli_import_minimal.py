from __future__ import annotations

import importlib
import sys

from sdetkit.cli import COMMANDS


def test_cli_import_does_not_eager_load_command_modules() -> None:
    modules = sorted({command.module for command in COMMANDS.values() if command.module})
    saved: dict[str, object] = {}
    for name in ["sdetkit.cli", *modules]:
        existing = sys.modules.pop(name, None)
        if existing is not None:
            saved[name] = existing
    try:
        importlib.import_module("sdetkit.cli")
        loaded = [name for name in modules if name in sys.modules]
        assert loaded == []
    finally:
        for name in ["sdetkit.cli", *modules]:
            sys.modules.pop(name, None)
        sys.modules.update(saved)
