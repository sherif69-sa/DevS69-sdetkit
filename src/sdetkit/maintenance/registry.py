from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from types import ModuleType
from typing import Any

from .types import CheckResult, MaintenanceContext

CheckRunner = Callable[[MaintenanceContext], CheckResult]


def discover_checks() -> list[tuple[str, CheckRunner, set[str]]]:
    from . import checks

    found: dict[str, tuple[CheckRunner, set[str]]] = {}
    for info in pkgutil.iter_modules(checks.__path__):
        if info.name.startswith("_"):
            continue
        module: ModuleType = importlib.import_module(f"{checks.__name__}.{info.name}")
        check_name = getattr(module, "CHECK_NAME", None)
        runner = getattr(module, "run", None)
        raw_modes: Any = getattr(module, "CHECK_MODES", {"quick", "full"})
        check_modes = (
            {str(item) for item in raw_modes}
            if isinstance(raw_modes, (set, list, tuple))
            else {"quick", "full"}
        )
        if isinstance(check_name, str) and callable(runner):
            found[check_name] = (runner, check_modes)
    return sorted(
        ((name, runner, modes) for name, (runner, modes) in found.items()), key=lambda item: item[0]
    )


def checks_for_mode(mode: str) -> list[tuple[str, CheckRunner]]:
    selected: list[tuple[str, CheckRunner]] = []
    for name, runner, check_modes in discover_checks():
        if mode in check_modes:
            selected.append((name, runner))
    return selected
