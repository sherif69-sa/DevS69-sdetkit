from __future__ import annotations

import base64
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


def test_apiget_auth_bearer_sets_authorization_header(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer SECRET"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/",
            "--auth",
            "bearer:SECRET",
            "--expect",
            "dict",
        ]
    )
    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"ok": True}
    assert out.err == ""


def test_apiget_auth_does_not_override_explicit_authorization_header(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer EXPLICIT"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/",
            "--header",
            "Authorization: Bearer EXPLICIT",
            "--auth",
            "bearer:OTHER",
            "--expect",
            "dict",
        ]
    )
    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"ok": True}
    assert out.err == ""


def test_apiget_auth_basic_sets_authorization_header(monkeypatch, capsys):
    user = "u"
    pwd = "p"
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == f"Basic {token}"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/",
            "--auth",
            "basic:u:p",
            "--expect",
            "dict",
        ]
    )
    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"ok": True}
    assert out.err == ""


def test_apiget_dump_headers_writes_to_stderr(monkeypatch, capsys):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, headers={"X-Foo": "bar"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(["apiget", "https://example.test/", "--dump-headers", "--expect", "dict"])
    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"ok": True}
    assert "http header:" in out.err.lower()
    assert "x-foo" in out.err.lower()
    assert "traceback" not in out.err.lower()


def test_apiget_print_status_for_post_and_non_2xx_is_clean(monkeypatch, capsys):
    seen = {"ok": 0, "bad": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ok":
            seen["ok"] += 1
            assert request.method == "POST"
            assert request.headers.get("content-type", "").startswith("application/json")
            return httpx.Response(200, json={"ok": True})
        seen["bad"] += 1
        assert request.method == "POST"
        return httpx.Response(404, json={"error": "nope"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/ok",
            "--method",
            "POST",
            "--json",
            '{"x": 1}',
            "--print-status",
            "--expect",
            "dict",
        ]
    )
    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"ok": True}
    assert "http status: 200" in out.err.lower()

    rc = cli.main(
        [
            "apiget",
            "https://example.test/bad",
            "--method",
            "POST",
            "--json",
            '{"x": 1}',
            "--print-status",
            "--expect",
            "dict",
        ]
    )
    assert rc == 1
    out = capsys.readouterr()
    assert out.out == ""
    err_lower = out.err.lower()
    assert "http status: 404" in err_lower
    assert "non-2xx response" in err_lower
    assert "traceback" not in err_lower
    assert seen == {"ok": 1, "bad": 1}


def test_apiget_paginate_with_header_still_paginates(monkeypatch, capsys):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.method == "GET"
        assert request.headers.get("x-test") == "ok"
        if request.url.path == "/page1":
            return httpx.Response(
                200,
                json=[1],
                headers={"Link": '<https://example.test/page2>; rel="next"'},
            )
        if request.url.path == "/page2":
            return httpx.Response(200, json=[2])
        raise AssertionError(f"unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(transport))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/page1",
            "--paginate",
            "--expect",
            "list",
            "--header",
            "X-Test: ok",
        ]
    )
    assert rc == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == [1, 2]
    assert out.err == ""
    assert calls == ["/page1", "/page2"]
