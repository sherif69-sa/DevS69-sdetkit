"""Compatibility alias for a legacy module name.

Use ``sdetkit.readiness_boost`` instead of ``sdetkit.phase_boost``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.readiness_boost")
_sys.modules[__name__] = _compat_alias
