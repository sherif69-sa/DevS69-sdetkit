"""Compatibility alias for a legacy module name.

Use ``sdetkit.baseline_hardening`` instead of ``sdetkit.phase1_hardening``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.baseline_hardening")
_sys.modules[__name__] = _compat_alias
