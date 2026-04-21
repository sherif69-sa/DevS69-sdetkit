"""Backward-compatible bool utilities re-export.

This module preserves legacy import paths after the bool helpers were
moved under ``sdetkit.utils``.
"""

from __future__ import annotations

from importlib import import_module as _import_module

_IMPL = _import_module("sdetkit.utils.bools")
__all__ = getattr(_IMPL, "__all__", [name for name in dir(_IMPL) if not name.startswith("__")])
globals().update({name: getattr(_IMPL, name) for name in __all__})
