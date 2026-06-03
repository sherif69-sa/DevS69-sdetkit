"""Compatibility wrapper for historical `sdetkit.phases.phase3_wrap_publication` imports."""

from __future__ import annotations

from .._compat_alias import alias_dir as _alias_dir
from .._compat_alias import alias_getattr as _alias_getattr
from .._compat_alias import export_module as _export_module
from .._compat_alias import install_module_alias as _install_module_alias

_TARGET = _export_module("sdetkit.phases.platform_readiness_wrap_publication", globals())


def __getattr__(name: str) -> object:
    return _alias_getattr(_TARGET, name)


def __dir__() -> list[str]:
    return _alias_dir(globals(), _TARGET)


_install_module_alias(__name__, _TARGET)
