from __future__ import annotations

import os

from .legacy_adapters import LEGACY_COMMAND_MODULES, LEGACY_NAMESPACE_COMMANDS


def legacy_hints_enabled() -> bool:
    raw = os.environ.get("SDETKIT_LEGACY_HINTS", "1")
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def legacy_preferred_surface(command: str) -> str:
    if command.startswith("weekly-review"):
        return "python -m sdetkit weekly-review"
    if command.startswith(("phase1-", "phase2-", "phase3-")):
        return "python -m sdetkit playbooks --help"
    if command.endswith("-closeout"):
        return "python -m sdetkit playbooks --help"
    return "python -m sdetkit kits list"


def legacy_deprecation_horizon(command: str) -> str:
    if command.startswith(("phase1-", "phase2-", "phase3-")):
        return "transition lane: migrate within 1-2 release cycles"
    if command.endswith("-closeout"):
        return "transition lane: migrate within 1-2 release cycles"
    if command.startswith("weekly-review"):
        return "compatibility lane: review migration quarterly"
    return "compatibility lane: migrate when feasible"


def legacy_migration_hint(command: str) -> str:
    preferred = legacy_preferred_surface(command)
    horizon = legacy_deprecation_horizon(command)
    return (
        f"[legacy-hint] '{command}' is a compatibility lane. "
        f"Preferred next surface: {preferred}. "
        f"Deprecation horizon: {horizon}. "
        "Canonical release-confidence path: python -m sdetkit gate fast -> gate release -> doctor."
    )
