"""Public package exports for sdetkit."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["ScalarFunctionRegistrationError", "register_scalar_function", "main_"]


def __getattr__(name: str) -> Any:
    if name in {"ScalarFunctionRegistrationError", "register_scalar_function"}:
        from .sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function

        exports = {
            "ScalarFunctionRegistrationError": ScalarFunctionRegistrationError,
            "register_scalar_function": register_scalar_function,
        }
        return exports[name]
    if name == "main_":
        return import_module(".__main__", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
