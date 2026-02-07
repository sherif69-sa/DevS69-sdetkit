import httpx
import pytest

from sdetkit.apiclient import fetch_json_dict


def test_trace_header_injected_and_retry_after_used_and_headers_not_mutated():
    delays: list[float] = []
    seen: list[str | None] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        seen.append(request.headers.get("X-Request-ID"))
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "5"}, json={"error": "rate"})
        return httpx.Response(200, json={"ok": True})

    def sleep(d: float) -> None:
        delays.append(d)

    transport = httpx.MockTransport(handler)
    headers = {"User-Agent": "sdetkit"}
    with httpx.Client(transport=transport, base_url="https://example.test") as client:
        data = fetch_json_dict(
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
    assert delays == [5.0]
    assert len(seen) == 2
    assert seen[0] is not None
    assert seen[0] == seen[1]


def test_request_error_retries_use_exponential_backoff_and_stop_after_success():
    delays: list[float] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    def sleep(d: float) -> None:
        delays.append(d)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="https://example.test") as client:
        data = fetch_json_dict(
            client,
            "/x",
            retries=3,
            backoff_base=0.5,
            backoff_factor=2.0,
            backoff_jitter=0.0,
            sleep=sleep,
        )

    assert data == {"ok": True}
    assert calls == 3
    assert delays == [0.5, 1.0]


def test_429_not_retried_by_default_even_when_retries_gt_1():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "1"}, json={"error": "rate"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="https://example.test") as client:
        with pytest.raises(RuntimeError):
            fetch_json_dict(client, "/x", retries=3)

    assert calls == 1
