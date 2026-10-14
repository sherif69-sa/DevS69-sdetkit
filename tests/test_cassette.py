from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from sdetkit.cassette import (
    AsyncCassetteRecordTransport,
    AsyncCassetteReplayTransport,
    Cassette,
    CassetteRecordTransport,
    CassetteReplayTransport,
)
from sdetkit.netclient import SdetAsyncHttpClient, SdetHttpClient
from sdetkit.security import SecurityError


def test_cassette_record_then_replay_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(200, json={"ok": True, "url": str(req.url)})

    inner = httpx.MockTransport(handler)
    cassette = Cassette()
    rec_transport = CassetteRecordTransport(cassette, inner)

    with httpx.Client(transport=rec_transport) as raw:
        c = SdetHttpClient(raw)
        got = c.get_json_dict("https://example.test/api")
        assert got["ok"] is True
        assert got["url"] == "https://example.test/api"

    cassette.save("sync.json")
    assert calls == ["https://example.test/api"]

    loaded = Cassette.load("sync.json")
    replay_transport = CassetteReplayTransport(loaded)

    with httpx.Client(transport=replay_transport) as raw2:
        c2 = SdetHttpClient(raw2)
        got2 = c2.get_json_dict("https://example.test/api")
        assert got2 == {"ok": True, "url": "https://example.test/api"}

    replay_transport.assert_exhausted()

    with httpx.Client(transport=CassetteReplayTransport(loaded)) as raw3:
        c3 = SdetHttpClient(raw3)
        with pytest.raises(RuntimeError):
            c3.get_json_dict("https://example.test/other")


def test_cassette_replay_ignores_dynamic_trace_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"trace": req.headers.get("X-Trace")})

    inner = httpx.MockTransport(handler)
    cassette = Cassette()
    rec_transport = CassetteRecordTransport(cassette, inner)

    with httpx.Client(transport=rec_transport) as raw:
        c = SdetHttpClient(raw, trace_header="X-Trace")
        v1 = c.get_json_dict("https://example.test/t")
        v2 = c.get_json_dict("https://example.test/t")
        assert isinstance(v1["trace"], str)
        assert isinstance(v2["trace"], str)
        assert v1["trace"] != v2["trace"]

    cassette.save("trace.json")

    loaded = Cassette.load("trace.json")
    rep = CassetteReplayTransport(loaded)

    with httpx.Client(transport=rep) as raw2:
        c2 = SdetHttpClient(raw2, trace_header="X-Trace")
        r1 = c2.get_json_dict("https://example.test/t")
        r2 = c2.get_json_dict("https://example.test/t")
        assert isinstance(r1["trace"], str)
        assert isinstance(r2["trace"], str)

    rep.assert_exhausted()


class _AsyncInner(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True, "url": str(request.url)})


@pytest.mark.asyncio
async def test_cassette_record_then_replay_async(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    inner = _AsyncInner()
    cassette = Cassette()
    rec_transport = AsyncCassetteRecordTransport(cassette, inner)

    async with httpx.AsyncClient(transport=rec_transport) as raw:
        c = SdetAsyncHttpClient(raw)
        got = await c.get_json_dict("https://example.test/a")
        assert got == {"ok": True, "url": "https://example.test/a"}

    cassette.save("async.json")
    assert inner.calls == ["https://example.test/a"]

    loaded = Cassette.load("async.json")
    replay_transport = AsyncCassetteReplayTransport(loaded)

    async with httpx.AsyncClient(transport=replay_transport) as raw2:
        c2 = SdetAsyncHttpClient(raw2)
        got2 = await c2.get_json_dict("https://example.test/a")
        assert got2 == {"ok": True, "url": "https://example.test/a"}

    replay_transport.assert_exhausted()

    async with httpx.AsyncClient(transport=AsyncCassetteReplayTransport(loaded)) as raw3:
        c3 = SdetAsyncHttpClient(raw3)
        with pytest.raises(RuntimeError):
            await c3.get_json_dict("https://example.test/other")


def test_cassette_save_and_load_block_traversal(tmp_path: Path, monkeypatch) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    cassette = Cassette()
    with pytest.raises(SecurityError):
        cassette.save("../escape.json")

    escaped = tmp_path / "escape.json"
    escaped.write_text('{"version": 1, "interactions": []}', encoding="utf-8")
    with pytest.raises(SecurityError):
        Cassette.load("../escape.json")
