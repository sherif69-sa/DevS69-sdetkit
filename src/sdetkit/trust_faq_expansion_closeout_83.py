"""Compatibility wrapper for historical `sdetkit.trust_faq_expansion_closeout_83` imports."""

from __future__ import annotations

from importlib import import_module as _import_module

_IMPL = _import_module("sdetkit.evidence.trust_faq_expansion_closeout_83")
__all__ = getattr(_IMPL, "__all__", [name for name in dir(_IMPL) if not name.startswith("__")])
globals().update({name: getattr(_IMPL, name) for name in __all__})
