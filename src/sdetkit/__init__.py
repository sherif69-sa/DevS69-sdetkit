"""Public package exports for sdetkit."""

from __future__ import annotations

from typing import Any

__all__ = ["ScalarFunctionRegistrationError", "register_scalar_function"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function

        exports = {
            "ScalarFunctionRegistrationError": ScalarFunctionRegistrationError,
            "register_scalar_function": register_scalar_function,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
