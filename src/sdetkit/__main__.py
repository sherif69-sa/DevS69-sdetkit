from __future__ import annotations

import sys

MIN_RUNTIME_PYTHON: tuple[int, int] = (3, 10)


def _validate_runtime_python() -> str | None:
    if sys.version_info >= MIN_RUNTIME_PYTHON:
        return None
    current = f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    required = f"{MIN_RUNTIME_PYTHON[0]}.{MIN_RUNTIME_PYTHON[1]}+"
    return (
        "sdetkit requires Python "
        f"{required}. Detected {current}. "
        "Use a 3.10+ interpreter before running the CLI."
    )


def _cassette_get(argv: list[str]) -> int:
    from .cassette_get import cassette_get

    return int(cassette_get(argv))


def _run_cli_main() -> int | None:
    from sdetkit.cli import main as cli_main

    return cli_main()


def main() -> int:
    version_error = _validate_runtime_python()
    if version_error is not None:
        sys.stderr.write(f"{version_error}\n")
        return 2

    argv = sys.argv
    if len(argv) > 1 and argv[1] == "cassette-get":
        try:
            return _cassette_get(argv[2:])
        except Exception as exc:  # pragma: no cover - defensive entrypoint handling
            sys.stderr.write(f"{exc}\n")
            return 2
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


if __name__ == "__main__":
    raise SystemExit(main())
