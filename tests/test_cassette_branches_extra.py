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
    open_transport,
)


def test_cassette_load_rejects_invalid_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    Path("bad_top.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="expected object"):
        Cassette.load("bad_top.json")

    Path("bad_inter.json").write_text('{"version": 1, "interactions": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="expected interactions list"):
        Cassette.load("bad_inter.json")


def test_replay_exhaustion_and_header_filtering_hits_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    cassette = Cassette()
    req = httpx.Request("GET", "https://example.test/api")
    resp = httpx.Response(200, headers={"X-K": "1"})
    cassette.append(req, resp, b"")

    cassette.interactions[0]["response"]["headers"] = [["X-K", "1"], "nope", ["X-BAD"], ["X-N", 3]]

    transport = CassetteReplayTransport(cassette)

    with httpx.Client(transport=transport) as client:
        r1 = client.get("https://example.test/api")
        assert r1.content == b""
        assert r1.headers.get("X-K") == "1"
        assert r1.headers.get("X-N") is None

        with pytest.raises(RuntimeError, match="no more recorded interactions"):
            client.get("https://example.test/api")


def test_replay_rejects_invalid_interaction_shape() -> None:
    cassette = Cassette([{"request": {}, "response": "nope"}])
    transport = CassetteReplayTransport(cassette)
    with pytest.raises(RuntimeError, match="invalid interaction shape"):
        transport.handle_request(httpx.Request("GET", "https://example.test/x"))


def test_replay_rejects_invalid_response_shape() -> None:
    cassette = Cassette(
        [
            {
                "request": {"method": "GET", "url": "https://example.test/bad", "body_b64": ""},
                "response": {"status_code": "200", "headers": [], "body_b64": ""},
            }
        ]
    )
    transport = CassetteReplayTransport(cassette)
    with pytest.raises(RuntimeError, match="invalid response shape"):
        transport.handle_request(httpx.Request("GET", "https://example.test/bad"))


@pytest.mark.asyncio
async def test_async_replay_aclose_raises_if_not_exhausted() -> None:
    cassette = Cassette(
        [
            {
                "request": {"method": "GET", "url": "https://example.test/a", "body_b64": ""},
                "response": {"status_code": 200, "headers": [], "body_b64": ""},
            }
        ]
    )
    transport = AsyncCassetteReplayTransport(cassette)
    with pytest.raises(AssertionError, match="cassette not exhausted"):
        await transport.aclose()


@pytest.mark.asyncio
async def test_async_replay_exhaustion_and_invalid_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    cassette = Cassette()
    req = httpx.Request("GET", "https://example.test/ok")
    resp = httpx.Response(200, headers={"X": "1"})
    cassette.append(req, resp, b"")

    t_ok = AsyncCassetteReplayTransport(cassette)
    async with httpx.AsyncClient(transport=t_ok) as client:
        r1 = await client.get("https://example.test/ok")
        assert r1.status_code == 200
        assert r1.content == b""
        with pytest.raises(RuntimeError, match="no more recorded interactions"):
            await client.get("https://example.test/ok")

    t_bad_it = AsyncCassetteReplayTransport(Cassette([{"request": {}, "response": None}]))
    with pytest.raises(RuntimeError, match="invalid interaction shape"):
        await t_bad_it.handle_async_request(httpx.Request("GET", "https://example.test/x"))

    t_bad_resp = AsyncCassetteReplayTransport(
        Cassette(
            [
                {
                    "request": {"method": "GET", "url": "https://example.test/r", "body_b64": ""},
                    "response": {"status_code": 200, "headers": "nope", "body_b64": ""},
                }
            ]
        )
    )
    with pytest.raises(RuntimeError, match="invalid response shape"):
        await t_bad_resp.handle_async_request(httpx.Request("GET", "https://example.test/r"))


class _AsyncInner(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.closed = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        return httpx.Response(200, content=b"ok")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_async_record_transport_saves_on_aclose_with_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    inner = _AsyncInner()
    cassette = Cassette()
    transport = AsyncCassetteRecordTransport(cassette, inner, path="rec.json")

    async with httpx.AsyncClient(transport=transport) as client:
        r = await client.get("https://example.test/save")
        assert r.status_code == 200

    p = Path("rec.json")
    assert p.exists()
    loaded = Cassette.load("rec.json")
    assert len(loaded.interactions) == 1
    assert inner.closed is True


def test_open_transport_auto_record_vs_replay_and_invalid_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    t1 = open_transport(
        "missing.json",
        mode="auto",
        upstream=httpx.MockTransport(lambda _: httpx.Response(200)),
    )
    assert isinstance(t1, CassetteRecordTransport)

    Path("have.json").write_text('{"version": 1, "interactions": []}', encoding="utf-8")
    t2 = open_transport("have.json", mode="auto")
    assert isinstance(t2, CassetteReplayTransport)

    with pytest.raises(ValueError):
        open_transport("x.json", mode="wat")
