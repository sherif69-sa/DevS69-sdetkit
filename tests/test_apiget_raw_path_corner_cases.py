from __future__ import annotations

import io
import json
from pathlib import Path

import httpx

from sdetkit import cli

_REAL_HTTPX_CLIENT = httpx.Client


def _client_factory(handler):
    def _mk(*a, **k):
        return _REAL_HTTPX_CLIENT(transport=httpx.MockTransport(handler))

    return _mk


def test_raw_path_preserves_retry_429_with_header_and_auth(monkeypatch, capsys):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                json={"err": "rate"},
                headers={"Retry-After": "0"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--print-status",
            "--expect",
            "dict",
            "--retries",
            "2",
            "--retry-429",
            "--header",
            "X-Test: ok",
            "--auth",
            "bearer:SECRET",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}
    assert "http status: 200" in out.err.lower()
    assert calls["n"] == 2


def test_raw_path_applies_trace_header_even_with_user_headers(monkeypatch, capsys):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["trace"] = request.headers.get("x-trace")
        seen["foo"] = request.headers.get("x-foo")
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--print-status",
            "--expect",
            "dict",
            "--trace-header",
            "X-Trace",
            "--request-id",
            "abc",
            "--header",
            "X-Foo: bar",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}
    assert seen == {"trace": "abc", "foo": "bar"}
    assert "http status: 200" in out.err.lower()


def test_data_at_file_binary_safe(monkeypatch, capsys, tmp_path: Path):
    payload = b"\xff\xfe\x00ABC\x10"
    p = tmp_path / "body.bin"
    p.write_bytes(payload)

    monkeypatch.chdir(tmp_path)

    seen = {"content": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content"] = request.content
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--method",
            "POST",
            "--data",
            "@body.bin",
            "--expect",
            "dict",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}
    assert out.err.strip() == ""
    assert seen["content"] == payload


def test_data_stdin_binary_safe(monkeypatch, capsys):
    from sdetkit import apiget

    payload = b"\xff\x00\xfeBIN\x10"

    class _FakeStdin:
        def __init__(self, b: bytes):
            self.buffer = io.BytesIO(b)

        def read(self) -> str:
            return payload.decode("latin1")

    monkeypatch.setattr(apiget.sys, "stdin", _FakeStdin(payload))

    seen = {"content": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content"] = request.content
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--method",
            "POST",
            "--data",
            "@-",
            "--expect",
            "dict",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}
    assert out.err.strip() == ""
    assert seen["content"] == payload


def test_expect_any_with_headers_makes_single_request(monkeypatch, capsys):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=[1, 2, 3], request=request)

    monkeypatch.setattr(httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--expect",
            "any",
            "--header",
            "X-Test: ok",
        ]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == [1, 2, 3]
    assert calls["n"] == 1
    assert out.err.strip() == ""
