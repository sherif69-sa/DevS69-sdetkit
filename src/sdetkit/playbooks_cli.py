"""Compatibility alias for historical ``sdetkit.playbooks_cli`` imports."""

from __future__ import annotations

import sys
from importlib import import_module

_IMPL = import_module("sdetkit.cli.playbooks_cli")
sys.modules[__name__] = _IMPL
