"""Top-level package exports and compatibility lazy-imports."""

from __future__ import annotations

import importlib
from types import ModuleType

_SUBPACKAGES = (
    "readiness",
    "phases",
    "evidence",
    "intelligence",
    "cli",
    "core",
    "gates",
    "ops",
    "utils",
)

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
    candidates = [_ALIAS_MAP.get(name, f"sdetkit.{name}")]
    candidates.extend(f"sdetkit.{subpackage}.{name}" for subpackage in _SUBPACKAGES)
    last_error: ModuleNotFoundError | None = None
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
            last_error = exc
            continue
        globals()[name] = module
        return module
    raise AttributeError(name) from last_error
