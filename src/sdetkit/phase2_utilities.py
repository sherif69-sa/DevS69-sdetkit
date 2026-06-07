"""Compatibility alias for a legacy module name.

Use ``sdetkit.release_readiness_utilities`` instead of ``sdetkit.phase2_utilities``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.release_readiness_utilities")
_sys.modules[__name__] = _compat_alias
