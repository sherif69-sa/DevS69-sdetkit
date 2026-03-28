"""Run sdetkit CLI via `python -m sdkit`."""

from sdetkit.cli import main

if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
