"""Compatibility wrapper for legacy module name.

Use ``sdetkit.example_asset2`` instead of ``sdetkit.demo_asset2``.
"""

from __future__ import annotations

from importlib import import_module as _import_module
from typing import Any as _Any

_COMPAT_MODULE_NAME = "sdetkit.example_asset2"
_compat_module = _import_module(_COMPAT_MODULE_NAME)


def __getattr__(name: str) -> _Any:
    return getattr(_compat_module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_compat_module)))


for _name in dir(_compat_module):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals().setdefault(_name, getattr(_compat_module, _name))

__all__ = [
    _name for _name in dir(_compat_module) if not (_name.startswith("__") and _name.endswith("__"))
]
