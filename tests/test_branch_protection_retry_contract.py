from __future__ import annotations

import importlib.util
import io
import urllib.error
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "enforce_branch_protection.py"
SPEC = importlib.util.spec_from_file_location("enforce_branch_protection_retry", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_request_retries_transient_github_api_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def _urlopen(*_: Any, **__: Any) -> _Response:
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(
                "https://api.github.test",
                503,
                "unavailable",
                {},
                io.BytesIO(b"temporarily unavailable"),
            )
        return _Response(b"{}")

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(MODULE.time, "sleep", sleeps.append)

    result = MODULE._request(
        token="token",
        method="PUT",
        url="https://api.github.test",
        payload={"strict": True},
    )

    assert result == {}
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_request_does_not_retry_non_transient_http_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def _urlopen(*_: Any, **__: Any) -> _Response:
        calls.append(1)
        raise urllib.error.HTTPError(
            "https://api.github.test",
            403,
            "forbidden",
            {},
            io.BytesIO(b"forbidden"),
        )

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(MODULE.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="GitHub API error 403"):
        MODULE._request(token="token", method="PUT", url="https://api.github.test")

    assert len(calls) == 1
    assert sleeps == []
