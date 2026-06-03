"""Compatibility alias for the professional naming migration."""

from __future__ import annotations

from ._compat_alias import alias_dir as _alias_dir
from ._compat_alias import alias_getattr as _alias_getattr
from ._compat_alias import export_module as _export_module

_TARGET = _export_module("sdetkit.phase2_wrap_handoff", globals())


def __getattr__(name: str) -> object:
    return _alias_getattr(_TARGET, name)


def __dir__() -> list[str]:
    return _alias_dir(globals(), _TARGET)
