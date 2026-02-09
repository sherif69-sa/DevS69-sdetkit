from __future__ import annotations

import json

import httpx

from sdetkit import apiget, cli

_REAL_HTTPX_CLIENT = httpx.Client


def _client_factory(transport: httpx.MockTransport):
    def _factory(*args, **kwargs):
        if kwargs.get("transport") is not None:
            return _REAL_HTTPX_CLIENT(*args, **kwargs)
        return _REAL_HTTPX_CLIENT(transport=transport)

    return _factory


def test_verbose_prints_request_and_response_meta_redacting_secrets(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer TOPSECRET"
        assert request.headers.get("X-Api-Key") == "SHOULD_NOT_LEAK"
        return httpx.Response(
            200,
            headers={"X-Req": "ok", "Set-Cookie": "a=b", "X-Api-Key": "SHOULD_NOT_LEAK"},
            json={"ok": True},
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/ok",
            "--verbose",
            "--auth",
            "bearer:TOPSECRET",
            "--header",
            "X-Api-Key:SHOULD_NOT_LEAK",
            "--expect",
            "any",
        ]
    )
    out = capsys.readouterr()

    assert rc == 0
    assert out.out == json.dumps({"ok": True}, sort_keys=True) + "\n"

    err = out.err
    low = err.lower()

    assert "http request:" in low
    assert "http response:" in low
    assert "authorization" in low
    assert "x-api-key" in low
    assert "<redacted>" in low

    assert "topsecret" not in low
    assert "should_not_leak" not in low
    assert "a=b" not in low


def test_debug_prints_traceback_on_transport_error(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(["apiget", "https://example.test/boom", "--debug", "--expect", "any"])
    out = capsys.readouterr()

    assert rc == 1
    assert out.out == ""
    assert "Traceback" in out.err, out.err
    assert "boom" in out.err


def test_verbose_does_not_print_traceback_on_transport_error(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(["apiget", "https://example.test/boom", "--verbose", "--expect", "any"])
    out = capsys.readouterr()

    assert rc == 1
    assert out.out == ""
    assert "Traceback" not in out.err
    assert "boom" in out.err
    assert "http request:" in out.err.lower(), out.err
