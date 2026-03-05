from __future__ import annotations

import httpx

from sdetkit import netclient


class _HeadersBoom:
    def get(self, key: str):
        raise RuntimeError("x")


def test_link_next_url_and_retry_after_and_merge_headers() -> None:
    req = httpx.Request("GET", "https://example.test/a")
    resp = httpx.Response(
        200,
        request=req,
        headers={"Link": '<b>; rel="prev", </n>; rel="next"'},
    )
    assert netclient._link_next_url(resp) == "https://example.test/n"

    assert netclient._retry_after_seconds({"Retry-After": "7"}) == 7.0
    assert netclient._retry_after_seconds(_HeadersBoom()) is None

    headers, rid = netclient._merge_headers({"A": "1"}, "X-Req", "id-1")
    assert headers == {"A": "1", "X-Req": "id-1"}
    assert rid == "id-1"


def test_emit_helpers_sync_and_async() -> None:
    seen = []
    ev = netclient.ClientEvent(type="complete", url="u", attempt=1, retries=1)
    netclient._emit(seen.append, ev)
    assert seen == [ev]
