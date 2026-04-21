"""Console script entry points for installed executables."""

from __future__ import annotations

from .apiget import main as _apiget_main
from .kvcli import cli_entry as _kvcli_main


def kvcli() -> int:
    return int(_kvcli_main())


def apigetcli() -> int:
    return int(_apiget_main())
