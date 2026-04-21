from __future__ import annotations

import sys


def _cassette_get(argv: list[str]) -> int:
    from .cassette_get import cassette_get

    return int(cassette_get(argv))


def _run_cli_main() -> int | None:
    from sdetkit.cli import main as cli_main

    return cli_main()


def main() -> int:
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
