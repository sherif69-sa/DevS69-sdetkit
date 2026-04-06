from __future__ import annotations

from typing import Any

_TRUE_VALUES = frozenset(
    {
        "1",
        "t",
        "true",
        "y",
        "yes",
        "on",
        "ok",
        "pass",
        "passed",
        "enabled",
        "enable",
        "active",
    }
)
_FALSE_VALUES = frozenset(
    {
        "0",
        "f",
        "false",
        "n",
        "no",
        "off",
        "fail",
        "failed",
        "error",
        "disabled",
        "disable",
        "inactive",
        "none",
        "null",
        "",
    }
)


def coerce_bool(value: Any, *, default: bool = False) -> bool:
    """Convert mixed scalar values into a deterministic boolean.

    This is intentionally stricter than ``bool(value)`` for strings so values
    like ``"false"`` or ``"inactive"`` are interpreted correctly.
    """

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
        try:
            return float(normalized) != 0.0
        except ValueError:
            pass
        return default
    return bool(value)
