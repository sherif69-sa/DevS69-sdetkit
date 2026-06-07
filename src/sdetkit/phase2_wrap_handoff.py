"""Compatibility alias for a legacy module name.

Use ``sdetkit.release_readiness_wrap_handoff`` instead of ``sdetkit.phase2_wrap_handoff``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.release_readiness_wrap_handoff")
_sys.modules[__name__] = _compat_alias
