from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType


def _load_toml_module() -> ModuleType:
    module_name = "tomllib" if sys.version_info >= (3, 11) else "tomli"
    return import_module(module_name)


_toml = _load_toml_module()
loads = _toml.loads
