"""Top-level package exports and compatibility lazy-imports."""

from __future__ import annotations

import importlib
from types import ModuleType

_ALIAS_MAP = {
    "gate": "sdetkit.gates.gate",
    "security_gate": "sdetkit.gates.security_gate",
    "playbooks_cli": "sdetkit.cli.playbooks_cli",
    "playbook_post_39": "sdetkit.cli.playbook_post_39",
    "serve": "sdetkit.cli.serve",
    "review_engine": "sdetkit.intelligence.review_engine",
    "review": "sdetkit.intelligence.review",
}


def __getattr__(name: str) -> ModuleType:
    module_name = _ALIAS_MAP.get(name, f"sdetkit.{name}")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise AttributeError(name) from exc
    globals()[name] = module
    return module
