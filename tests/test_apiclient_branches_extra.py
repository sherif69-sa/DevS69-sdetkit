from __future__ import annotations

import httpx
import pytest

from sdetkit import apiclient


def test_sync_pagination_cycle_and_limit_errors() -> None:
    def cycle(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1], headers={"Link": '</x>; rel="next"'}, request=req)

    with httpx.Client(transport=httpx.MockTransport(cycle)) as c:
        with pytest.raises(RuntimeError):
            apiclient.fetch_json_list_paginated(c, "https://example.test/x", max_pages=3)

    state = {"n": 0}

    def chain(req: httpx.Request) -> httpx.Response:
        state["n"] += 1
        nxt = f"/p{state['n'] + 1}"
        return httpx.Response(
            200, json=[state["n"]], headers={"Link": f"<{nxt}>; rel=next"}, request=req
        )

    with httpx.Client(transport=httpx.MockTransport(chain)) as c:
        with pytest.raises(RuntimeError):
            apiclient.fetch_json_list_paginated(c, "https://example.test/p1", max_pages=1)


@pytest.mark.asyncio
async def test_async_pagination_cycle_and_value_guards() -> None:
    def cycle(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1], headers={"Link": '</x>; rel="next"'}, request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(cycle)) as c:
        with pytest.raises(RuntimeError):
            await apiclient.fetch_json_list_paginated_async(
                c, "https://example.test/x", max_pages=3
            )

    async with httpx.AsyncClient(transport=httpx.MockTransport(cycle)) as c:
        with pytest.raises(ValueError):
            await apiclient.fetch_json_list_paginated_async(c, "https://example.test/x", retries=0)

    with pytest.raises(ValueError):
        apiclient.fetch_json_list_paginated(httpx.Client(), "https://example.test/x", max_pages=0)
