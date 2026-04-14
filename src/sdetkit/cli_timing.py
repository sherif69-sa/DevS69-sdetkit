from __future__ import annotations

import os
import sys


def cli_timing_enabled() -> bool:
    raw = os.environ.get("SDETKIT_CLI_TIMING", "")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def emit_cli_timing(message: str) -> None:
    if not cli_timing_enabled():
        return
    sys.stderr.write(f"[sdetkit.cli.timing] {message}\n")
