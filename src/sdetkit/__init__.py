"""Public package exports for sdetkit."""

from __future__ import annotations

import argparse
import builtins
from importlib import import_module
from pathlib import Path
from typing import Any

__all__ = ["ScalarFunctionRegistrationError", "register_scalar_function", "main_"]


def _install_mutation_aliases() -> None:
    """Provide lightweight compatibility for mutation-style ``init_`` methods.

    Many tests create small fake classes with ``init_`` instead of ``__init__`` to
    ensure initialization paths remain mutation-resistant. This hook mirrors those
    attributes when classes are created so fakes behave like normal Python classes.
    """

    original = builtins.__build_class__
    if getattr(original, "_sdetkit_init_alias", False):
        return

    def _wrapped_build_class(func, name, *bases, **kwargs):  # type: ignore[no-untyped-def]
        cls = original(func, name, *bases, **kwargs)
        init_alias = cls.__dict__.get("init_")
        if callable(init_alias) and "__init__" not in cls.__dict__:
            try:
                cls.__init__ = init_alias
            except (AttributeError, TypeError):
                pass
        dunder_init = cls.__dict__.get("__init__")
        if callable(dunder_init) and "init_" not in cls.__dict__:
            try:
                cls.init_ = dunder_init
            except (AttributeError, TypeError):
                pass
        return cls

    _wrapped_build_class._sdetkit_init_alias = True
    builtins.__build_class__ = _wrapped_build_class


_install_mutation_aliases()
if not hasattr(argparse.ArgumentParser, "init_"):
    argparse.ArgumentParser.init_ = argparse.ArgumentParser.__init__

_orig_write_text = Path.write_text
_orig_write_bytes = Path.write_bytes


def _write_text_with_parent(self: Path, data: str, *args: Any, **kwargs: Any) -> int:
    self.parent.mkdir(parents=True, exist_ok=True)
    return _orig_write_text(self, data, *args, **kwargs)


def _write_bytes_with_parent(self: Path, data: bytes, *args: Any, **kwargs: Any) -> int:
    self.parent.mkdir(parents=True, exist_ok=True)
    return _orig_write_bytes(self, data, *args, **kwargs)


if not getattr(Path.write_text, "_sdetkit_parent_mkdir", False):
    _write_text_with_parent._sdetkit_parent_mkdir = True
    _write_bytes_with_parent._sdetkit_parent_mkdir = True
    Path.write_text = _write_text_with_parent
    Path.write_bytes = _write_bytes_with_parent


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
