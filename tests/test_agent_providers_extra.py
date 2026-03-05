from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.agent.providers import CachedProvider, FakeProvider, LocalHTTPProvider


class _HTTPResponse:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


def test_local_http_provider_prefers_response_text(monkeypatch) -> None:
    payload: dict[str, object] = {}

    def _fake_urlopen(req, timeout):
        payload["url"] = req.full_url
        payload["body"] = json.loads(req.data.decode("utf-8"))
        return _HTTPResponse('{"response": "ok"}')

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    provider = LocalHTTPProvider(endpoint="https://example.test/complete", model="m")

    out = provider.complete(role="manager", task="do", context={"x": 1})

    assert out == "ok"
    assert payload["url"] == "https://example.test/complete"
    assert payload["body"] == {"model": "m", "prompt": "[manager] do", "context": {"x": 1}}


def test_local_http_provider_non_json_response(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _HTTPResponse("plain text"))
    provider = LocalHTTPProvider(endpoint="https://example.test/complete", model="m")
    assert provider.complete(role="worker", task="x", context={}) == "plain text"


@pytest.mark.parametrize("raw", ['{"text":"t"}', '{"output":"o"}', '{"x":1}'])
def test_local_http_provider_fallback_fields(monkeypatch, raw: str) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _HTTPResponse(raw))
    provider = LocalHTTPProvider(endpoint="https://example.test/complete", model="m")
    out = provider.complete(role="worker", task="x", context={})
    assert out in {"t", "o", raw}


def test_cached_provider_handles_invalid_cache_payload(tmp_path: Path) -> None:
    wrapped = FakeProvider(suffix="fresh")
    cached = CachedProvider(wrapped=wrapped, cache_dir=tmp_path / "cache")
    key = cached._cache_key(role="r", task="t", context={"a": 1})

    cache_file = tmp_path / "cache" / f"{key}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("[]", encoding="utf-8")

    assert cached.complete(role="r", task="t", context={"a": 1}) == "r:t:fresh"

    cache_file.write_text("{bad", encoding="utf-8")
    assert cached.complete(role="r", task="t", context={"a": 1}) == "r:t:fresh"
