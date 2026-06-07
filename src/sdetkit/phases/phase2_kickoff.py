"""Compatibility alias for a legacy module name.

Use ``sdetkit.phases.release_readiness_kickoff`` instead of ``sdetkit.phases.phase2_kickoff``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.phases.release_readiness_kickoff")
_sys.modules[__name__] = _compat_alias
