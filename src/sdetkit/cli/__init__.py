"""CLI package compatibility wrappers."""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType


def _load_legacy_cli_module() -> ModuleType:
    module_path = Path(__file__).resolve().parent.parent / "cli.py"
    spec = importlib.util.spec_from_file_location("sdetkit._legacy_cli_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CLI module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_module_main(module_name: str, args: list[str]) -> int:
    module = _load_legacy_cli_module()
    return int(module._run_module_main(module_name, args))


def __getattr__(name: str):
    module = _load_legacy_cli_module()
    return getattr(module, name)


def main(argv: Sequence[str] | None = None) -> int:
    module = _load_legacy_cli_module()
    module._run_module_main = _run_module_main
    return int(module.main(argv))
