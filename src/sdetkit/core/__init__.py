"""Public package exports for sdetkit."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = ["ScalarFunctionRegistrationError", "register_scalar_function", "main_"]

if TYPE_CHECKING:
    from . import __main__ as main_
    from .sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function

_main_module: Any | None = None


def __getattr__(name: str) -> Any:
    global _main_module
    if name in {"ScalarFunctionRegistrationError", "register_scalar_function"}:
        from .sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function

        exports = {
            "ScalarFunctionRegistrationError": ScalarFunctionRegistrationError,
            "register_scalar_function": register_scalar_function,
        }
        return exports[name]
    if name == "main_":
        if _main_module is None:
            _main_module = import_module(".__main__", __name__)
        return _main_module
    try:
        return import_module(f".{name}", __name__)
    except ImportError as exc:
        raise AttributeError(name) from exc
