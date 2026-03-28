from __future__ import annotations

from .cli import main

if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
