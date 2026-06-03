from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType


def export_module(target_module: str, namespace: dict[str, object]) -> ModuleType:
    module = import_module(target_module)
    raw_all = getattr(module, "__all__", None)
    if raw_all is None:
        exports = [name for name in dir(module) if not name.startswith("__")]
    else:
        exports = [str(name) for name in raw_all]

    namespace["__all__"] = exports
    namespace["_ALIAS_TARGET_MODULE"] = module

    for name in exports:
        namespace[name] = getattr(module, name)

    return module


def alias_getattr(module: ModuleType, name: str) -> object:
    return getattr(module, name)


def alias_dir(namespace: dict[str, object], module: ModuleType) -> list[str]:
    exported = namespace.get("__all__", [])
    export_names = [str(name) for name in exported] if isinstance(exported, list) else []
    return sorted(set(namespace) | set(export_names) | set(dir(module)))


def install_module_alias(alias_name: str, module: ModuleType) -> ModuleType:
    sys.modules[alias_name] = module
    return module
