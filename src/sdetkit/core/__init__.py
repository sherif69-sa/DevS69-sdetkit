"""Public package exports for sdetkit."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

__all__ = ["ScalarFunctionRegistrationError", "register_scalar_function", "main_"]

if TYPE_CHECKING:
    from . import __main__ as main_
    from .sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function

_main_module: Any | None = None
_missing_module_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    global _main_module
    if name in {"ScalarFunctionRegistrationError", "register_scalar_function"}:
        from .sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function

        exports = {
            "ScalarFunctionRegistrationError": ScalarFunctionRegistrationError,
            "register_scalar_function": register_scalar_function,
        }
        return exports[name]
    if name == "main_":
        if _main_module is None:
            _main_module = import_module(".__main__", __name__)
        return _main_module
    try:
        return import_module(f".{name}", __name__)
    except ImportError:
        pass

    pkg_dir = Path(__file__).resolve().parent
    numbered_candidates = sorted(pkg_dir.glob(f"{name}_*.py"))
    if len(numbered_candidates) == 1:
        return import_module(f".{numbered_candidates[0].stem}", __name__)

    compat_aliases = {
        "weekly_review": "weekly_review",
        "upgrade_hub": "upgrade_hub",
        "kits": "kits",
    }
    alias_target = compat_aliases.get(name)
    if alias_target and alias_target != name:
        return import_module(f".{alias_target}", __name__)

    if name not in _missing_module_cache:
        playbooks_cli = import_module("sdetkit.playbooks_cli")

        class _CompatModule(ModuleType):
            def main(self, argv: list[str] | None = None) -> int:
                from ._runtime import ensure_supported_python

                unsupported_rc = ensure_supported_python(component="sdetkit core")
                if unsupported_rc is not None:
                    return unsupported_rc
                args = list(argv or [])
                cmd = name.replace("_", "-")
                return playbooks_cli.main([cmd, *args])

        _missing_module_cache[name] = _CompatModule(name)
    return _missing_module_cache[name]
