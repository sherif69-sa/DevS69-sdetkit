import httpx

from sdetkit.netclient import ClientEvent, RetryPolicy, SdetHttpClient


def test_observability_events_include_sleep_and_complete_ok_and_same_request_id():
    events: list[ClientEvent] = []
    sleeps: list[float] = []
    t = 0.0

    def clock() -> float:
        return t

    def sleep(d: float) -> None:
        nonlocal t
        sleeps.append(d)
        t += d

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json=[0])
        return httpx.Response(200, json=[1])

    transport = httpx.MockTransport(handler)
    pol = RetryPolicy(retries=3, retry_on_429=True, backoff_base=0.5, backoff_jitter=0.0)

    with httpx.Client(transport=transport, base_url="https://example.test") as raw:
        c = SdetHttpClient(
            raw,
            retry=pol,
            trace_header="X-Request-ID",
            hook=events.append,
            clock=clock,
            sleep=sleep,
        )
        out = c.get_json_list("/x")

    assert out == [1]
    assert sleeps == [2.0]
    assert any(e.type == "sleep" and e.sleep_seconds == 2.0 for e in events)
    completes = [e for e in events if e.type == "complete"]
    assert completes and completes[-1].ok is True
    rid = [e.request_id for e in events if e.request_id is not None][0]
    assert all(e.request_id == rid for e in events if e.request_id is not None)


def test_observability_retry_on_request_error_emits_attempt_error_and_sleep():
    events: list[ClientEvent] = []
    sleeps: list[float] = []

    def sleep(d: float) -> None:
        sleeps.append(d)

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    pol = RetryPolicy(retries=3, backoff_base=0.5, backoff_factor=2.0, backoff_jitter=0.0)

    with httpx.Client(transport=transport, base_url="https://example.test") as raw:
        c = SdetHttpClient(raw, retry=pol, hook=events.append, sleep=sleep)
        out = c.get_json_dict("/x")

    assert out == {"ok": True}
    assert sleeps == [0.5, 1.0]
    assert any(e.type == "attempt_error" and e.error == "request_error" for e in events)
