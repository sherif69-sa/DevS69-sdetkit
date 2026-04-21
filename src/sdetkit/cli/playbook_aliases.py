from __future__ import annotations

from importlib import import_module
from typing import cast


def resolve_non_day_playbook_alias(cmd: str) -> str:
    """Resolve product/legacy playbook names to a parser-backed command."""
    try:
        playbooks_cli = import_module("sdetkit.playbooks_cli")
        cmd_to_mod, alias_to_canonical = cast(
            tuple[dict[str, str], dict[str, str]],
            playbooks_cli._build_registry(playbooks_cli._pkg_dir()),
        )
    except Exception:
        return cmd

    if cmd in alias_to_canonical and cmd in cmd_to_mod and not cmd.startswith("impact"):
        return alias_to_canonical[cmd]
    return cmd
