from __future__ import annotations

import json

import httpx
import pytest

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

    for k in ["accept:", "accept-encoding:", "connection:", "host:", "user-agent:"]:
        assert k not in low

    assert "http request:" in low

    assert "http request curl:" in low

    assert "curl" in low

    assert "authorization: <redacted>" in low

    assert "x-api-key: <redacted>" in low

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


def test_verbose_keeps_user_agent_when_user_provided(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("User-Agent") == "MINE"
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/ok",
            "--verbose",
            "--header",
            "User-Agent: MINE",
            "--expect",
            "any",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    low = out.err.lower()
    assert "user-agent: mine" in low


def test_apiget_allow_scheme_insecure_and_query_errors(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "file://example.test/x",
            "--allow-scheme",
            "file",
            "--insecure",
            "--expect",
            "dict",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert "tls verification disabled" in out.err.lower()

    with pytest.raises(SystemExit):
        cli.main(["apiget", "https://example.test/x", "--query", "bad", "--expect", "dict"])


def test_apiget_exception_handlers_timeout_circuit_and_value(monkeypatch, capsys):
    class _FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _RaisesTimeout:
        def __init__(self, *_a, **_k):
            pass

        def get_json_any(self, *_a, **_k):
            raise TimeoutError("x")

    class _RaisesCircuit:
        def __init__(self, *_a, **_k):
            pass

        def get_json_any(self, *_a, **_k):
            raise apiget.CircuitOpenError("open")

    class _RaisesValue:
        def __init__(self, *_a, **_k):
            pass

        def get_json_any(self, *_a, **_k):
            raise ValueError("bad json")

    monkeypatch.setattr(apiget.httpx, "Client", _FakeClient)
    monkeypatch.setattr(apiget, "SdetHttpClient", _RaisesTimeout)
    rc = cli.main(["apiget", "https://example.test/x", "--verbose", "--expect", "any"])
    err = capsys.readouterr().err.lower()
    assert rc == 2
    assert "request timed out" in err

    monkeypatch.setattr(apiget, "SdetHttpClient", _RaisesCircuit)
    rc = cli.main(["apiget", "https://example.test/x", "--verbose", "--expect", "any"])
    err = capsys.readouterr().err.lower()
    assert rc == 2
    assert "circuit open" in err

    monkeypatch.setattr(apiget, "SdetHttpClient", _RaisesValue)
    rc = cli.main(["apiget", "https://example.test/x", "--verbose", "--expect", "any"])
    err = capsys.readouterr().err.lower()
    assert rc == 1
    assert "bad json" in err
