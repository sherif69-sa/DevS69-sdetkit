"""Compatibility wrapper for the legacy phase sequential executor path.

Use ``scripts/readiness_sequential_executor.py`` instead.
"""

from __future__ import annotations

import importlib.util as _importlib_util
import runpy as _runpy
from pathlib import Path as _Path

_COMPAT_ALIAS_PATH = _Path(__file__).with_name("readiness_sequential_executor.py")

_spec = _importlib_util.spec_from_file_location(
    "_sdetkit_readiness_sequential_executor",
    _COMPAT_ALIAS_PATH,
)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Unable to load readiness executor from {_COMPAT_ALIAS_PATH}")

_compat_alias = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_compat_alias)

for _name in dir(_compat_alias):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals().setdefault(_name, getattr(_compat_alias, _name))

if __name__ == "__main__":
    if hasattr(_compat_alias, "main"):
        raise SystemExit(_compat_alias.main())
    _runpy.run_path(str(_COMPAT_ALIAS_PATH), run_name="__main__")
