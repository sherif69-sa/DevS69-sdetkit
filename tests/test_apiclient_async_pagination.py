import httpx
import pytest

from sdetkit.apiclient import fetch_json_list_paginated_async


@pytest.mark.asyncio
async def test_fetch_json_list_paginated_async_follows_link_next_and_keeps_trace_id():
    seen_ids: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_ids.append(request.headers.get("X-Request-ID"))
        page = request.url.params.get("page", "1")
        if page == "1":
            return httpx.Response(
                200,
                headers={"Link": '</items?page=2>; rel="next"'},
                json=[1],
            )
        if page == "2":
            return httpx.Response(
                200,
                headers={"Link": '</items?page=3>; rel="next"'},
                json=[2],
            )
        return httpx.Response(200, json=[3])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        out = await fetch_json_list_paginated_async(
            client,
            "/items?page=1",
            retries=2,
            trace_header="X-Request-ID",
        )

    assert out == [1, 2, 3]
    assert len(seen_ids) == 3
    assert seen_ids[0] is not None
    assert seen_ids[0] == seen_ids[1] == seen_ids[2]
