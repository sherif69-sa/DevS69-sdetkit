from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

_REAL_HTTPX_CLIENT = httpx.Client


def _client_factory(handler):
    def _factory(*a, **k):
        return _REAL_HTTPX_CLIENT(transport=httpx.MockTransport(handler))

    return _factory


def test_apiget_data_at_file(monkeypatch, capsys, tmp_path: Path):
    from sdetkit import apiget, cli

    url = "https://example.test/x"
    p = tmp_path / "body.txt"
    p.write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.content == b"hello"
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(["apiget", url, "--method", "POST", "--data", "@body.txt", "--expect", "dict"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err.strip() == ""
    assert json.loads(out.out) == {"ok": True}


def test_apiget_json_at_file(monkeypatch, capsys, tmp_path: Path):
    from sdetkit import apiget, cli

    url = "https://example.test/x"
    p = tmp_path / "body.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {"a": 1}
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(["apiget", url, "--method", "POST", "--json", "@body.json", "--expect", "dict"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err.strip() == ""
    assert json.loads(out.out) == {"ok": True}


def test_apiget_at_file_missing_is_clean_error(capsys):
    from sdetkit import cli

    url = "https://example.test/x"
    rc = cli.main(
        ["apiget", url, "--method", "POST", "--data", "@/nope/missing.txt", "--expect", "dict"]
    )
    out = capsys.readouterr()
    assert rc == 1
    assert out.out.strip() == ""
    assert "file not found" in out.err
    assert "Traceback" not in out.err


def test_apiget_at_file_absolute_path_requires_flag(monkeypatch, capsys, tmp_path: Path):
    from sdetkit import apiget, cli

    p = tmp_path / "abs.txt"
    p.write_text("secret", encoding="utf-8")

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not run")

    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--method",
            "POST",
            "--data",
            f"@{p}",
            "--expect",
            "dict",
        ]
    )
    out = capsys.readouterr()
    assert rc == 1
    assert out.out.strip() == ""
    assert "file not found" in out.err


def test_apiget_at_file_blocks_traversal(monkeypatch, capsys, tmp_path: Path):
    from sdetkit import apiget, cli

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not run")

    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--method",
            "POST",
            "--data",
            "@../outside.txt",
            "--expect",
            "dict",
        ]
    )
    out = capsys.readouterr()
    assert rc == 1
    assert out.out.strip() == ""
    assert "file not found" in out.err


def test_apiget_data_at_stdin_dash_reads_text(monkeypatch, capsys):
    from sdetkit import apiget, cli

    class _Stdin:
        def read(self) -> str:
            return "hello-stdin"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b"hello-stdin"
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(
        apiget,
        "sys",
        type(
            "S",
            (),
            {
                "stdin": _Stdin(),
                "stderr": apiget.sys.stderr,
                "stdout": apiget.sys.stdout,
                "argv": apiget.sys.argv,
            },
        )(),
    )
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(
        ["apiget", "https://example.test/x", "--method", "POST", "--data", "@-", "--expect", "dict"]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}


def test_apiget_at_file_empty_path_is_clean_error(capsys):
    from sdetkit import cli

    rc = cli.main(
        ["apiget", "https://example.test/x", "--method", "POST", "--data", "@", "--expect", "dict"]
    )
    out = capsys.readouterr()
    assert rc == 1
    assert out.out.strip() == ""
    assert "cannot read file: <empty path>" in out.err


def test_apiget_stdin_bytes_uses_buffer_when_available(monkeypatch, capsys):
    from sdetkit import apiget, cli

    class _Buf:
        def read(self):
            return b"BYTES"

    class _Stdin:
        buffer = _Buf()

        def read(self) -> str:
            return "fallback-text"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b"BYTES"
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(
        apiget,
        "sys",
        type(
            "S",
            (),
            {
                "stdin": _Stdin(),
                "stderr": apiget.sys.stderr,
                "stdout": apiget.sys.stdout,
                "argv": apiget.sys.argv,
            },
        )(),
    )
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(
        ["apiget", "https://example.test/x", "--method", "POST", "--data", "@-", "--expect", "dict"]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}


def test_apiget_stdin_bytes_falls_back_when_no_buffer(monkeypatch, capsys):
    from sdetkit import apiget, cli

    class _Stdin:
        def read(self) -> str:
            return "TEXT"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b"TEXT"
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(
        apiget,
        "sys",
        type(
            "S",
            (),
            {
                "stdin": _Stdin(),
                "stderr": apiget.sys.stderr,
                "stdout": apiget.sys.stdout,
                "argv": apiget.sys.argv,
            },
        )(),
    )
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(
        ["apiget", "https://example.test/x", "--method", "POST", "--data", "@-", "--expect", "dict"]
    )
    out = capsys.readouterr()
    assert rc == 0
    assert json.loads(out.out) == {"ok": True}


def test_apiget_stdin_bytes_oserror_is_clean_error(monkeypatch, capsys):
    from sdetkit import apiget, cli

    class _Buf:
        def read(self):
            raise OSError("boom")

    class _Stdin:
        buffer = _Buf()

        def read(self) -> str:
            return "TEXT"

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not run")

    monkeypatch.setattr(
        apiget,
        "sys",
        type(
            "S",
            (),
            {
                "stdin": _Stdin(),
                "stderr": apiget.sys.stderr,
                "stdout": apiget.sys.stdout,
                "argv": apiget.sys.argv,
            },
        )(),
    )
    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc = cli.main(
        ["apiget", "https://example.test/x", "--method", "POST", "--data", "@-", "--expect", "dict"]
    )
    out = capsys.readouterr()
    assert rc == 1
    assert out.out.strip() == ""
    assert "cannot read stdin bytes" in out.err
    assert "boom" in out.err


def test_apiget_auth_bearer_and_basic_validation(monkeypatch, capsys):
    from sdetkit import apiget, cli

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") is not None
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(apiget.httpx, "Client", _client_factory(handler))

    rc1 = cli.main(["apiget", "https://example.test/x", "--auth", "bearer:ABC", "--expect", "dict"])
    out1 = capsys.readouterr()
    assert rc1 == 0
    assert json.loads(out1.out) == {"ok": True}

    rc2 = cli.main(
        ["apiget", "https://example.test/x", "--auth", "basic:user:pass", "--expect", "dict"]
    )
    out2 = capsys.readouterr()
    assert rc2 == 0
    assert json.loads(out2.out) == {"ok": True}


def test_apiget_auth_errors_are_clean(capsys):
    from sdetkit import cli

    with pytest.raises(SystemExit) as e1:
        cli.main(["apiget", "https://example.test/x", "--auth", "bearer:", "--expect", "any"])
    out1 = capsys.readouterr()
    assert int(e1.value.code) == 2
    assert out1.out.strip() == ""
    assert "auth bearer token is required" in out1.err

    with pytest.raises(SystemExit) as e2:
        cli.main(
            ["apiget", "https://example.test/x", "--auth", "basic:useronly", "--expect", "any"]
        )
    out2 = capsys.readouterr()
    assert int(e2.value.code) == 2
    assert out2.out.strip() == ""
    assert "auth basic credentials must be USER:PASS" in out2.err

    with pytest.raises(SystemExit) as e3:
        cli.main(["apiget", "https://example.test/x", "--auth", "wat:abc", "--expect", "any"])
    out3 = capsys.readouterr()
    assert int(e3.value.code) == 2
    assert out3.out.strip() == ""
    assert "auth scheme must be bearer or basic" in out3.err

    with pytest.raises(SystemExit) as e4:
        cli.main(["apiget", "https://example.test/x", "--auth", "bearer:ba\nd", "--expect", "any"])
    out4 = capsys.readouterr()
    assert int(e4.value.code) == 2
    assert out4.out.strip() == ""
    assert "invalid auth bearer token" in out4.err


def test_apiget_sensitive_header_detector():
    from sdetkit import apiget

    assert apiget._is_sensitive_header("Authorization")
    assert apiget._is_sensitive_header("X-Api-Key")
    assert apiget._is_sensitive_header("x_apikey")
    assert apiget._is_sensitive_header("X-Token")
    assert apiget._is_sensitive_header("Password")
    assert apiget._is_sensitive_header("Secret-Value")
    assert not apiget._is_sensitive_header("X-Request-Id")
