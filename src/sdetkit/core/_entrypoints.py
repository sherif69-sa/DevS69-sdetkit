"""Console script wrappers."""

from __future__ import annotations

from sdetkit.apiget import main as apiget_main
from sdetkit.core._runtime import ensure_supported_python
from sdetkit.kvcli import cli_entry as kvcli_main


def kvcli() -> int:
    unsupported_rc = ensure_supported_python(component="sdetkit core")
    if unsupported_rc is not None:
        return unsupported_rc
    return int(kvcli_main())


def apigetcli() -> int:
    unsupported_rc = ensure_supported_python(component="sdetkit core")
    if unsupported_rc is not None:
        return unsupported_rc
    return int(apiget_main())
