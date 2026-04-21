"""Compatibility module alias for mutation-oriented coverage tests."""

from __future__ import annotations

import sys

from .atomicio import atomic_write_text
from .cassette_get import cassette_get as _cassette_get_impl
from .security import SecurityError, safe_path


def _cassette_get(argv: list[str]) -> int:
    import sdetkit.cassette_get as mod

    # keep monkeypatchability on this compatibility module.
    mod.atomic_write_text = atomic_write_text
    mod.safe_path = safe_path
    mod.SecurityError = SecurityError
    return int(_cassette_get_impl(argv))


def main() -> int:
    argv = sys.argv
    if len(argv) > 1 and argv[1] == "cassette-get":
        try:
            return _cassette_get(argv[2:])
        except Exception as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
    from .__main__ import _run_cli_main

    try:
        code = _run_cli_main()
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        sys.stderr.write(f"{exc.code}\n")
        return 1
    return 0 if code is None else int(code)


__all__ = ["main", "_cassette_get", "atomic_write_text", "safe_path", "SecurityError"]
