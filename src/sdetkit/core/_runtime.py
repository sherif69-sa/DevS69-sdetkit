from __future__ import annotations

import sys
from typing import TextIO

MIN_RUNTIME_PYTHON: tuple[int, int] = (3, 11)


def ensure_supported_python(
    *,
    component: str = "sdetkit core",
    version_info: tuple[int, int] | None = None,
    stderr: TextIO | None = None,
) -> int | None:
    if version_info is None:
        current = (sys.version_info[0], sys.version_info[1])
    else:
        current = version_info
    if current >= MIN_RUNTIME_PYTHON:
        return None
    stream = stderr or sys.stderr
    required = f"{MIN_RUNTIME_PYTHON[0]}.{MIN_RUNTIME_PYTHON[1]}+"
    stream.write(
        f"{component} requires Python {required}. "
        f"Detected {current[0]}.{current[1]}. Use a {required} interpreter before running.\n"
    )
    return 2
