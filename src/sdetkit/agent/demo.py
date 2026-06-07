"""Compatibility alias for a legacy module name.

Use ``sdetkit.agent.example`` instead of ``sdetkit.agent.demo``.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_compat_alias = _import_module("sdetkit.agent.example")
_sys.modules[__name__] = _compat_alias
