from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .legacy_commands import (
    LEGACY_NAMESPACE_COMMANDS,
    legacy_deprecation_horizon,
    legacy_hints_enabled,
    legacy_migration_hint,
    legacy_preferred_surface,
)


def emit_legacy_migration_hint(command: str) -> None:
    if not legacy_hints_enabled():
        return
    sys.stderr.write(legacy_migration_hint(command) + "\n")


def run_legacy_migrate_hint(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit legacy migrate-hint")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("command", nargs="?")
    ns = parser.parse_args(list(argv))
    if not ns.command and not ns.all:
        sys.stderr.write("legacy error: expected command name after migrate-hint (or pass --all)\n")
        return 2
    if ns.command and ns.all:
        sys.stderr.write("legacy error: use either <command> or --all for migrate-hint\n")
        return 2
    commands = [str(ns.command)] if ns.command else list(LEGACY_NAMESPACE_COMMANDS)
    items = [
        {
            "command": command,
            "preferred_surface": legacy_preferred_surface(command),
            "deprecation_horizon": legacy_deprecation_horizon(command),
            "canonical_path": ["gate fast", "gate release", "doctor"],
            "hint": legacy_migration_hint(command),
        }
        for command in commands
    ]
    if ns.format == "json":
        if len(items) == 1:
            payload = {"schema_version": "1", "mode": "single", **items[0]}
        else:
            payload = {"schema_version": "1", "mode": "all", "count": len(items), "items": items}
        sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
        return 0
    sys.stdout.write("\n".join(item["hint"] for item in items) + "\n")
    return 0
