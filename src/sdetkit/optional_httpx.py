"""Utility for optional `httpx` loading in environments without network extras."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any

__all__ = ["load_httpx"]


def _missing_message(feature: str) -> str:
    return (
        "httpx is required for "
        f"{feature}; install optional network dependencies."
    )


def _build_missing_httpx_module(*, feature: str) -> Any:
    message = _missing_message(feature)

    class _MissingHttpxModule:
        class TimeoutException(Exception):
            pass

        class HTTPError(Exception):
            pass

        class RequestError(Exception):
            pass

        class Response:
            status_code = 0

        class URL:
            def __str__(self) -> str:
                return ""

        class Client:  # pragma: no cover - defensive fallback only
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

        class AsyncClient:  # pragma: no cover - defensive fallback only
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

        class HTTPTransport:  # pragma: no cover - defensive fallback only
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

        class AsyncHTTPTransport:  # pragma: no cover - defensive fallback only
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

        class MockTransport:  # pragma: no cover - defensive fallback only
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

    return _MissingHttpxModule()


def load_httpx(*, feature: str = "network workflows") -> Any:
    if importlib.util.find_spec("httpx") is not None:
        return importlib.import_module("httpx")
    return _build_missing_httpx_module(feature=feature)
