from __future__ import annotations

import httpx
import pytest

from sdetkit import netclient


@pytest.mark.asyncio
async def test_emit_async_and_async_client_error_paths() -> None:
    seen = []

    async def hook(ev: netclient.ClientEvent):
        seen.append(ev.type)

    await netclient._emit_async(
        hook, netclient.ClientEvent(type="attempt_start", url="u", attempt=0, retries=1)
    )
    assert seen == ["attempt_start"]

    async def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as raw:
        c = netclient.SdetAsyncHttpClient(raw, retry=netclient.RetryPolicy(retries=1))
        with pytest.raises(RuntimeError):
            await c.get_json_dict("https://example.test/x")
