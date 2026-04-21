"""Backward-compatible review module surface."""

from __future__ import annotations

from .intelligence import review as review_impl

__all__ = getattr(review_impl, "__all__", [name for name in dir(review_impl) if not name.startswith("_")])
globals().update({name: getattr(review_impl, name) for name in __all__})
