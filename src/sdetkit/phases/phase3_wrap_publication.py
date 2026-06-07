"""Compatibility alias for a legacy module name.

Use ``sdetkit.phases.platform_readiness_wrap_publication`` instead of ``sdetkit.phases.phase3_wrap_publication``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.phases.platform_readiness_wrap_publication")
_sys.modules[__name__] = _compat_alias
