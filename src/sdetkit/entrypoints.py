from __future__ import annotations

import sys

from sdetkit.cli import main


def kvcli() -> None:
    sys.argv = ["kvcli", "kv", *sys.argv[1:]]
    raise SystemExit(main())


def apigetcli() -> None:
    sys.argv = ["apigetcli", "apiget", *sys.argv[1:]]
    raise SystemExit(main())
