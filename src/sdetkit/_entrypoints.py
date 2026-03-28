"""Console script wrappers."""

from __future__ import annotations

from .apiget import main as apiget_main
from .kvcli import main as kvcli_main


def kvcli() -> int:
    return kvcli_main()


def apigetcli() -> int:
    return apiget_main()
