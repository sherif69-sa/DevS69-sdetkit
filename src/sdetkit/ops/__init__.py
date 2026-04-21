"""Ops public API."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run_workflow(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .ops import run_workflow as _run_workflow

    return _run_workflow(*args, **kwargs)


def create_server(*args: Any, **kwargs: Any) -> Any:
    from .ops import create_server as _create_server

    return _create_server(*args, **kwargs)


def main(argv: list[str] | None = None) -> int:
    from .ops import main as _main

    return int(_main(argv))


def _sanitize_workflow_filename(path: Path) -> str:
    from .ops import _sanitize_workflow_filename as _impl

    return _impl(path)


__all__ = ["_sanitize_workflow_filename", "create_server", "main", "run_workflow"]
