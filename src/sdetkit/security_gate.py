"""Compatibility wrapper for historical `sdetkit.security_gate` imports."""

from __future__ import annotations

from importlib import import_module as _import_module
from typing import Any

_IMPL = _import_module("sdetkit.gates.security_gate")
__all__ = getattr(_IMPL, "__all__", [name for name in dir(_IMPL) if not name.startswith("__")])
globals().update({name: getattr(_IMPL, name) for name in __all__})


def main(argv: list[str] | None = None) -> int:
    """Forward-compatible entrypoint that respects wrapper-level monkeypatching."""
    if "_run_ruff_fix" in globals():
        impl: Any = _IMPL
        impl._run_ruff_fix = globals()["_run_ruff_fix"]
    return int(_IMPL.main(argv))


def __getattr__(name: str) -> Any:
    return getattr(_IMPL, name)
