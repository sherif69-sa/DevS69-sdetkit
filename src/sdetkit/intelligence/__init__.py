"""Compatibility wrappers for the ``sdetkit intelligence`` command surface."""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType


def _load_legacy_intelligence_module() -> ModuleType:
    module_path = Path(__file__).resolve().parent.parent / "intelligence.py"
    spec = importlib.util.spec_from_file_location(
        "sdetkit._legacy_intelligence_module", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load intelligence module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def __getattr__(name: str) -> ModuleType:
    for candidate in (f"sdetkit.intelligence.{name}", f"sdetkit.{name}"):
        try:
            module = importlib.import_module(candidate)
            globals()[name] = module
            return module
        except ModuleNotFoundError:
            continue
    raise AttributeError(name)


def main(argv: Sequence[str] | None = None) -> int:
    module = _load_legacy_intelligence_module()
    return int(module.main(list(argv) if argv is not None else None))
