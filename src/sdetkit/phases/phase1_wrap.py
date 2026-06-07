"""Compatibility alias for a legacy module name.

Use ``sdetkit.phases.baseline_wrap`` instead of ``sdetkit.phases.phase1_wrap``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.phases.baseline_wrap")
_sys.modules[__name__] = _compat_alias
