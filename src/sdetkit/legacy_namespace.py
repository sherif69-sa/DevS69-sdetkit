from __future__ import annotations

import sys
from collections.abc import Sequence

from .legacy_cli import run_legacy_migrate_hint
from .legacy_commands import LEGACY_NAMESPACE_COMMANDS


def handle_legacy_namespace(argv: Sequence[str]) -> int | None:
    if not argv or argv[0] != "legacy":
        return None
    if len(argv) == 1:
        sys.stderr.write("legacy error: expected a legacy command name\n")
        return 2
    if argv[1] == "list":
        sys.stdout.write("\n".join(LEGACY_NAMESPACE_COMMANDS) + "\n")
        return 0
    if argv[1] == "migrate-hint":
        return run_legacy_migrate_hint(list(argv[2:]))
    return None
