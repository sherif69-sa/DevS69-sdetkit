from __future__ import annotations

from importlib import metadata


def tool_version() -> str:
    try:
        return metadata.version("sdetkit")
    except metadata.PackageNotFoundError:
        return "0+unknown"
