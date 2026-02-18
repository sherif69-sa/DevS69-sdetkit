from __future__ import annotations

import httpx

from sdetkit import apiget, cli


def test_apiget_cassette_record_then_replay(tmp_path, capsys, monkeypatch):
    cassette = tmp_path / "apiget.cassette"
    monkeypatch.chdir(tmp_path)
    url = "https://example.test/x"

    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "url": str(request.url)},
            request=request,
        )

    monkeypatch.setattr(
        apiget.httpx, "HTTPTransport", lambda *a, **k: httpx.MockTransport(ok_handler)
    )

    rc1 = cli.main(
        [
            "apiget",
            url,
            "--expect",
            "dict",
            "--cassette",
            "apiget.cassette",
            "--cassette-mode",
            "record",
        ]
    )
    out1 = capsys.readouterr().out
    assert rc1 == 0
    assert cassette.exists()
    assert cassette.stat().st_size > 0
    assert "ok" in out1

    def bad_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network/transport used during replay")

    monkeypatch.setattr(
        apiget.httpx, "HTTPTransport", lambda *a, **k: httpx.MockTransport(bad_handler)
    )

    rc2 = cli.main(
        [
            "apiget",
            url,
            "--expect",
            "dict",
            "--cassette",
            "apiget.cassette",
            "--cassette-mode",
            "replay",
        ]
    )
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert "ok" in out2


def test_apiget_record_failure_does_not_write_empty_cassette(tmp_path, capsys, monkeypatch):
    cassette = tmp_path / "apiget.cassette"
    monkeypatch.chdir(tmp_path)
    url = "https://example.test/x"

    def fail_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    monkeypatch.setattr(
        apiget.httpx, "HTTPTransport", lambda *a, **k: httpx.MockTransport(fail_handler)
    )

    rc = cli.main(
        [
            "apiget",
            url,
            "--expect",
            "dict",
            "--cassette",
            "apiget.cassette",
            "--cassette-mode",
            "record",
        ]
    )
    _ = capsys.readouterr()

    assert rc != 0
    assert not cassette.exists()


def test_apiget_replay_missing_cassette_is_error(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)

    rc = cli.main(
        [
            "apiget",
            "https://example.test/x",
            "--expect",
            "dict",
            "--cassette",
            "missing.cassette",
            "--cassette-mode",
            "replay",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "cassette not found" in captured.err


def test_apiget_replay_requires_exhausted_cassette(tmp_path, capsys, monkeypatch):
    from sdetkit.cassette import Cassette

    url = "https://example.test/x"
    monkeypatch.chdir(tmp_path)

    req = httpx.Request("GET", url)
    body = b'{"ok": true}'
    resp = httpx.Response(200, content=body, request=req)

    c = Cassette([])
    c.append(req, resp, body)
    c.append(req, resp, body)
    c.save("apiget.cassette")

    rc = cli.main(
        [
            "apiget",
            url,
            "--expect",
            "dict",
            "--cassette",
            "apiget.cassette",
            "--cassette-mode",
            "replay",
        ]
    )

    out = capsys.readouterr()
    assert rc == 1
    assert out.out.strip() == ""
    assert "cassette not exhausted" in out.err
    assert "Traceback" not in out.err
