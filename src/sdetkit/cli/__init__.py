"""CLI package compatibility wrappers."""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

from ..versioning import tool_version

# Exposed for compatibility: tests and downstream callers monkeypatch these names.
__all__ = ["import_module", "tool_version", "_run_module_main", "main"]


_def_cached: ModuleType | None = None


def _load_legacy_cli_module() -> ModuleType:
    global _def_cached
    if _def_cached is not None:
        return _def_cached
    module_path = Path(__file__).resolve().parent.parent / "cli.py"
    spec = importlib.util.spec_from_file_location("sdetkit._legacy_cli_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CLI module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "_sdetkit_orig_run_module_main"):
        module._sdetkit_orig_run_module_main = module._run_module_main
    _def_cached = module
    return module


def _sync_compat_bindings(module: Any) -> None:
    """Keep compatibility-layer monkeypatch targets wired into legacy module."""
    module.import_module = import_module
    module.tool_version = tool_version


def _run_module_main(module_name: str, args: Sequence[str]) -> int:
    module = _load_legacy_cli_module()
    _sync_compat_bindings(module)
    return int(module._sdetkit_orig_run_module_main(module_name, list(args)))


def __getattr__(name: str):
    module = _load_legacy_cli_module()
    _sync_compat_bindings(module)
    return getattr(module, name)


def main(argv: Sequence[str] | None = None) -> int:
    module = _load_legacy_cli_module()
    _sync_compat_bindings(module)
    module._run_module_main = globals().get("_run_module_main", _run_module_main)
    return int(module.main(argv))
