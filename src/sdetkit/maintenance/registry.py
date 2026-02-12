from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from types import ModuleType

from .types import CheckResult, MaintenanceContext

CheckRunner = Callable[[MaintenanceContext], CheckResult]


def discover_checks() -> list[tuple[str, CheckRunner]]:
    from . import checks

    found: dict[str, CheckRunner] = {}
    for info in pkgutil.iter_modules(checks.__path__):
        if info.name.startswith("_"):
            continue
        module: ModuleType = importlib.import_module(f"{checks.__name__}.{info.name}")
        check_name = getattr(module, "CHECK_NAME", None)
        runner = getattr(module, "run", None)
        if isinstance(check_name, str) and callable(runner):
            found[check_name] = runner
    return sorted(found.items(), key=lambda item: item[0])


def checks_for_mode(mode: str) -> list[tuple[str, CheckRunner]]:
    selected: list[tuple[str, CheckRunner]] = []
    for name, runner in discover_checks():
        check_modes = getattr(runner, "modes", {"quick", "full"})
        if mode in check_modes:
            selected.append((name, runner))
    return selected
