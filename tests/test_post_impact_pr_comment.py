from __future__ import annotations

import io
from typing import Any
from urllib.error import HTTPError

import pytest

from scripts import post_impact_pr_comment
from scripts.post_impact_pr_comment import (
    MARKER,
    _api_request,
    _compose_comment_body,
    _find_existing_comment_id,
    upsert_comment,
)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_compose_comment_body_includes_marker() -> None:
    body = _compose_comment_body("hello")
    assert MARKER in body
    assert "hello" in body


def test_find_existing_comment_id_returns_marked_comment() -> None:
    comments = [
        {"id": 10, "body": "random"},
        {"id": 99, "body": f"prefix\n{MARKER}\ncontent"},
    ]
    assert _find_existing_comment_id(comments) == 99


def test_api_request_retries_transient_github_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def fake_urlopen(*_: Any, **__: Any) -> _Response:
        calls.append(1)
        if len(calls) < 3:
            raise HTTPError(
                url="https://api.github.com",
                code=503,
                msg="Unavailable",
                hdrs=None,
                fp=io.BytesIO(b"temporarily unavailable"),
            )
        return _Response(b"[]")

    monkeypatch.setattr(post_impact_pr_comment.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(post_impact_pr_comment.time, "sleep", sleeps.append)

    assert _api_request("https://api.github.com", "token") == []
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_api_request_does_not_retry_non_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def fake_urlopen(*_: Any, **__: Any) -> _Response:
        calls.append(1)
        raise HTTPError(
            url="https://api.github.com",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(b"forbidden"),
        )

    monkeypatch.setattr(post_impact_pr_comment.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(post_impact_pr_comment.time, "sleep", sleeps.append)

    with pytest.raises(HTTPError) as exc_info:
        _api_request("https://api.github.com", "token")

    assert exc_info.value.code == 403
    assert len(calls) == 1
    assert sleeps == []


def test_upsert_comment_dry_run_short_circuits_network() -> None:
    status = upsert_comment("owner/repo", 12, "token", "body", dry_run=True)
    assert status == "dry_run"


def test_upsert_comment_returns_forbidden_on_403(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_api_request(*_args: object, **_kwargs: object) -> object:
        raise HTTPError(url="https://api.github.com", code=403, msg="Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(post_impact_pr_comment, "_api_request", fake_api_request)
    status = upsert_comment("owner/repo", 12, "token", "body", dry_run=False)
    assert status == "forbidden"
