"""Compatibility loader for `httpx`.

`httpx` is a runtime dependency, but this module keeps a defensive fallback for
degraded environments where imports are partially unavailable.
"""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any

__all__ = ["load_httpx"]


def _missing_message(feature: str) -> str:
    return f"httpx is required for {feature}; install runtime dependencies (for example: pip install -e .)."


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
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

        class URL:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ModuleNotFoundError(message)

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
