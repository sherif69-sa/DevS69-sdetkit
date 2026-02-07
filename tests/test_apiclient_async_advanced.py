import httpx
import pytest

from sdetkit.apiclient import fetch_json_dict_async


@pytest.mark.asyncio
async def test_async_trace_header_injected_and_retry_after_used_and_headers_not_mutated():
    delays: list[float] = []
    seen: list[str | None] = []
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        seen.append(request.headers.get("X-Request-ID"))
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": "rate"})
        return httpx.Response(200, json={"ok": True})

    async def sleep(d: float) -> None:
        delays.append(d)

    transport = httpx.MockTransport(handler)
    headers = {"User-Agent": "sdetkit"}
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        data = await fetch_json_dict_async(
            client,
            "/x",
            retries=3,
            headers=headers,
            trace_header="X-Request-ID",
            retry_on_429=True,
            sleep=sleep,
        )

    assert data == {"ok": True}
    assert headers == {"User-Agent": "sdetkit"}
    assert delays == [3.0]
    assert len(seen) == 2
    assert seen[0] is not None
    assert seen[0] == seen[1]


@pytest.mark.asyncio
async def test_async_request_error_retries_use_exponential_backoff_and_stop_after_success():
    delays: list[float] = []
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    async def sleep(d: float) -> None:
        delays.append(d)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        data = await fetch_json_dict_async(
            client,
            "/x",
            retries=3,
            backoff_base=0.25,
            backoff_factor=2.0,
            backoff_jitter=0.0,
            sleep=sleep,
        )

    assert data == {"ok": True}
    assert calls == 3
    assert delays == [0.25, 0.5]
