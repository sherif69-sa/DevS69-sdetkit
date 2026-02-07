import httpx
import pytest

from sdetkit.apiclient import fetch_json_list_async


@pytest.mark.asyncio
async def test_fetch_json_list_async_success_and_trace_header():
    seen: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-Request-ID"))
        return httpx.Response(200, json=["a", "b"])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        out = await fetch_json_list_async(
            client, "/x", trace_header="X-Request-ID", request_id="abc"
        )

    assert out == ["a", "b"]
    assert seen == ["abc"]


@pytest.mark.asyncio
async def test_fetch_json_list_async_rejects_non_list_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"x": 1})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        with pytest.raises(ValueError):
            await fetch_json_list_async(client, "/x")
