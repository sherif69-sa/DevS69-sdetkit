from __future__ import annotations

import json
from pathlib import Path

import httpx

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
