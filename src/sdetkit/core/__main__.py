from __future__ import annotations

import sys
from importlib import import_module

from sdetkit.core._runtime import ensure_supported_python


def _ensure_supported_python(version_info: tuple[int, int] | None = None) -> int | None:
    return ensure_supported_python(
        component="sdetkit core",
        version_info=version_info,
    )


def _cassette_get(argv: list[str]) -> int:
    _cassette_get_module = import_module("sdetkit.cassette_get")
    from sdetkit.atomicio import atomic_write_text
    from sdetkit.security import SecurityError, safe_path

    # Compatibility shim for tests that monkeypatch __main__ symbols directly.
    _cassette_get_module.atomic_write_text = atomic_write_text
    _cassette_get_module.safe_path = safe_path
    _cassette_get_module.SecurityError = SecurityError  # type: ignore[misc]
    return _cassette_get_module.cassette_get(argv)


def main() -> int:
    unsupported_rc = _ensure_supported_python()
    if unsupported_rc is not None:
        return unsupported_rc

    argv = sys.argv[1:]
    if argv and argv[0] == "cassette-get":
        try:
            return _cassette_get(argv[1:])
        except Exception as e:
            sys.stderr.write(str(e) + "\n")
            return 2

    from sdetkit.cli import main as cli_main

    try:
        return int(cli_main() or 0)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return int(code)
        sys.stderr.write(f"{code}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
