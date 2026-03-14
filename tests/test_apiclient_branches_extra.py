from __future__ import annotations

import httpx
import pytest

from sdetkit import apiclient


def test_sync_pagination_cycle_and_limit_errors() -> None:
    def impact(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1], headers={"Link": '</x>; rel="next"'}, request=req)

    with httpx.Client(transport=httpx.MockTransport(impact)) as c:
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
    def impact(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1], headers={"Link": '</x>; rel="next"'}, request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(impact)) as c:
        with pytest.raises(RuntimeError):
            await apiclient.fetch_json_list_paginated_async(
                c, "https://example.test/x", max_pages=3
            )

    async with httpx.AsyncClient(transport=httpx.MockTransport(impact)) as c:
        with pytest.raises(ValueError):
            await apiclient.fetch_json_list_paginated_async(c, "https://example.test/x", retries=0)

    with pytest.raises(ValueError):
        apiclient.fetch_json_list_paginated(httpx.Client(), "https://example.test/x", max_pages=0)


def test_fetch_json_dict_and_list_error_paths_sync() -> None:
    sleeps: list[float] = []

    def sleep(d: float) -> None:
        sleeps.append(d)

    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if req.url.path == "/dict429" and calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, request=req)
        if req.url.path == "/dictbad":
            return httpx.Response(200, json=[1], request=req)
        if req.url.path == "/listbad":
            return httpx.Response(200, json={"x": 1}, request=req)
        if req.url.path == "/non2xx":
            return httpx.Response(500, request=req)
        return httpx.Response(200, json={"ok": True}, request=req)

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        out = apiclient.fetch_json_dict(
            c,
            "https://example.test/dict429",
            retries=2,
            retry_on_429=True,
            sleep=sleep,
        )
        assert out == {"ok": True}
        assert sleeps == [2.0]

        with pytest.raises(ValueError):
            apiclient.fetch_json_dict(c, "https://example.test/dictbad")
        with pytest.raises(ValueError):
            apiclient.fetch_json_list(c, "https://example.test/listbad")
        with pytest.raises(RuntimeError):
            apiclient.fetch_json_list(c, "https://example.test/non2xx")


@pytest.mark.asyncio
async def test_fetch_json_list_response_async_branches() -> None:
    slept: list[float] = []

    async def sleep(d: float) -> None:
        slept.append(d)

    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if req.url.path == "/rate" and calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, request=req)
        if req.url.path == "/badtype":
            return httpx.Response(200, json={"oops": True}, request=req)
        if req.url.path == "/status":
            return httpx.Response(503, request=req)
        return httpx.Response(200, json=[1], request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        data = await apiclient.fetch_json_list_async(
            c,
            "https://example.test/rate",
            retries=2,
            retry_on_429=True,
            sleep=sleep,
        )
        assert data == [1]
        assert slept == [3.0]

        with pytest.raises(ValueError):
            await apiclient.fetch_json_list_async(c, "https://example.test/badtype")
        with pytest.raises(RuntimeError):
            await apiclient.fetch_json_list_async(c, "https://example.test/status")


def test_paginated_helpers_trace_header_and_limit() -> None:
    seen_headers: list[str | None] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_headers.append(req.headers.get("X-Trace"))
        if req.url.path == "/p1":
            return httpx.Response(200, json=[1], headers={"Link": '</p2>; rel="next"'}, request=req)
        if req.url.path == "/p2":
            return httpx.Response(200, json=[2], headers={"Link": '</p3>; rel="next"'}, request=req)
        return httpx.Response(200, json=[3], request=req)

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(RuntimeError):
            apiclient.fetch_json_list_paginated(
                c,
                "https://example.test/p1",
                max_pages=2,
                trace_header="X-Trace",
                request_id="rid-1",
            )

    assert seen_headers and all(h == "rid-1" for h in seen_headers)
