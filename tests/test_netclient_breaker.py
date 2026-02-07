import httpx
import pytest

from sdetkit.netclient import CircuitBreaker, CircuitOpenError, RetryPolicy, SdetHttpClient


def test_circuit_breaker_opens_and_then_allows_after_reset():
    now = 0.0

    def clock() -> float:
        return now

    calls = 0

    def bad_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"err": True})

    br = CircuitBreaker(failure_threshold=2, reset_seconds=10.0)
    pol = RetryPolicy(retries=1)

    transport_bad = httpx.MockTransport(bad_handler)
    with httpx.Client(transport=transport_bad, base_url="https://example.test") as raw_bad:
        c1 = SdetHttpClient(raw_bad, retry=pol, breaker=br, clock=clock)
        with pytest.raises(RuntimeError):
            c1.get_json_dict("/x")
        with pytest.raises(RuntimeError):
            c1.get_json_dict("/x")
        with pytest.raises(CircuitOpenError):
            c1.get_json_dict("/x")

    now = 11.0

    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport_ok = httpx.MockTransport(ok_handler)
    with httpx.Client(transport=transport_ok, base_url="https://example.test") as raw_ok:
        c2 = SdetHttpClient(raw_ok, retry=pol, breaker=br, clock=clock)
        assert c2.get_json_dict("/x") == {"ok": True}
        assert c2.get_json_dict("/x") == {"ok": True}
