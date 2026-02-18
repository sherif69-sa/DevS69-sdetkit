from __future__ import annotations

import json

import httpx
import pytest

import sdetkit.apiget as apiget
from sdetkit import cli
from sdetkit.netclient import RetryPolicy, SdetHttpClient

_REAL_HTTPX_CLIENT = httpx.Client


def _client_factory(transport: httpx.BaseTransport):
    def _make_client(*args, **kwargs):
        if kwargs.get("transport") is not None:
            return _REAL_HTTPX_CLIENT(*args, **kwargs)
        return _REAL_HTTPX_CLIENT(transport=transport)

    return _make_client


def test_apiget_paginate_envelope_mode_accumulates_items(monkeypatch, capsys):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/items" and request.url.query == b"page=2":
            return httpx.Response(200, json={"items": [{"id": 2}], "next": None})
        if request.url.path == "/items" and request.url.query == b"":
            return httpx.Response(
                200,
                json={"items": [{"id": 1}], "next": "?page=2"},
            )
        raise AssertionError(f"unexpected request url: {request.url}")

    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(httpx.MockTransport(handler)))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/items",
            "--paginate",
            "--paginate-mode",
            "envelope",
            "--expect",
            "list",
        ]
    )

    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == [{"id": 1}, {"id": 2}]
    assert out.err == ""
    assert calls == ["https://example.test/items", "https://example.test/items?page=2"]


def test_apiget_paginate_envelope_mode_validates_keys(monkeypatch, capsys):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "apiget",
                "https://example.test/items",
                "--paginate",
                "--paginate-mode",
                "envelope",
                "--paginate-items-key",
                "",
            ]
        )

    assert exc.value.code == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert "paginate-items-key must not be empty" in out.err


def test_netclient_envelope_pagination_cycle_and_shape_errors():
    responses = {
        "https://example.test/items": {"items": [1], "next": "?page=2"},
        "https://example.test/items?page=2": {"items": [2], "next": "/items"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = responses.get(str(request.url))
        if payload is None:
            raise AssertionError(f"unexpected url: {request.url}")
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as raw:
        client = SdetHttpClient(raw, retry=RetryPolicy(retries=1))
        with pytest.raises(RuntimeError, match="pagination cycle"):
            client.get_json_list_paginated_envelope("https://example.test/items", max_pages=4)

    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"items": "bad"}))
    ) as raw:
        client = SdetHttpClient(raw, retry=RetryPolicy(retries=1))
        with pytest.raises(ValueError, match="expected json array at key 'items'"):
            client.get_json_list_paginated_envelope("https://example.test/items")
