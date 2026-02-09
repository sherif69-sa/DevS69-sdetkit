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


def test_apiget_fail_suppresses_body_and_returns_rc_1(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "nope"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        ["apiget", "https://example.test/bad", "--fail", "--print-status", "--expect", "any"]
    )
    out = capsys.readouterr()

    assert rc == 1
    assert out.out.strip() == ""
    assert "http status: 404" in out.err
    assert "http error: 404" in out.err
    assert "Traceback" not in out.err


def test_apiget_fail_with_body_prints_body_and_returns_rc_1(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "nope"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(["apiget", "https://example.test/bad", "--fail-with-body", "--expect", "any"])
    out = capsys.readouterr()

    assert rc == 1
    assert json.loads(out.out) == {"error": "nope"}
    assert "http error: 404" in out.err
    assert "Traceback" not in out.err
