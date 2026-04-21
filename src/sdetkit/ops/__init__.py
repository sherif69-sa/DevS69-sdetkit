"""Ops public API."""

from __future__ import annotations

from typing import Any


def run_workflow(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from sdetkit.ops.ops import run_workflow as _run_workflow

    return _run_workflow(*args, **kwargs)


def create_server(*args: Any, **kwargs: Any) -> Any:
    from sdetkit.ops.ops import create_server as _create_server

    return _create_server(*args, **kwargs)


__all__ = ["create_server", "run_workflow"]
