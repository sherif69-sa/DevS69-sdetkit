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


def test_cassette_record_then_replay_sync(tmp_path: Path) -> None:
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

    p = tmp_path / "sync.json"
    cassette.save(p)
    assert calls == ["https://example.test/api"]

    loaded = Cassette.load(p)
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


def test_cassette_replay_ignores_dynamic_trace_header(tmp_path: Path) -> None:
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

    p = tmp_path / "trace.json"
    cassette.save(p)

    loaded = Cassette.load(p)
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
async def test_cassette_record_then_replay_async(tmp_path: Path) -> None:
    inner = _AsyncInner()
    cassette = Cassette()
    rec_transport = AsyncCassetteRecordTransport(cassette, inner)

    async with httpx.AsyncClient(transport=rec_transport) as raw:
        c = SdetAsyncHttpClient(raw)
        got = await c.get_json_dict("https://example.test/a")
        assert got == {"ok": True, "url": "https://example.test/a"}

    p = tmp_path / "async.json"
    cassette.save(p)
    assert inner.calls == ["https://example.test/a"]

    loaded = Cassette.load(p)
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
