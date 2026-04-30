from __future__ import annotations

import sys
from collections.abc import Sequence

from .legacy_cli import run_legacy_migrate_hint
from .legacy_commands import LEGACY_NAMESPACE_COMMANDS


def _write_legacy_help() -> None:
    sys.stdout.write(
        "usage: sdetkit legacy [-h] {list,migrate-hint,<legacy-command>} ...\n"
        "\n"
        "Access historical and closeout compatibility lanes.\n"
        "\n"
        "positional arguments:\n"
        "  list              list contained legacy commands\n"
        "  migrate-hint      show migration guidance for a legacy command\n"
        "  <legacy-command>  run a contained legacy command\n"
        "\n"
        "options:\n"
        "  -h, --help        show this help message and exit\n"
    )


def handle_legacy_namespace(argv: Sequence[str]) -> int | None:
    if not argv or argv[0] != "legacy":
        return None
    if len(argv) == 1:
        _write_legacy_help()
        return 0
    if argv[1] in {"-h", "--help"}:
        _write_legacy_help()
        return 0
    if argv[1] == "list":
        sys.stdout.write("\n".join(LEGACY_NAMESPACE_COMMANDS) + "\n")
        return 0
    if argv[1] == "migrate-hint":
        return run_legacy_migrate_hint(list(argv[2:]))
    if argv[1] in LEGACY_NAMESPACE_COMMANDS:
        return None
    sys.stderr.write(f"legacy error: unknown subcommand '{argv[1]}'\n")
    return 2
