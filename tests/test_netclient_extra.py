from __future__ import annotations

import httpx
import pytest

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


def test_http_client_request_retries_request_error_backoff(monkeypatch):
    attempts = {"n": 0}
    slept = []

    def _sleep(d: float) -> None:
        slept.append(d)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        assert request.headers.get("A") == "1"
        assert request.headers.get("X-Req") == "rid1"
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pol = netclient.RetryPolicy(retries=2, backoff_base=0.1, backoff_factor=1.0, backoff_jitter=0.0)
    hc = netclient.SdetHttpClient(client, retry=pol, trace_header="X-Req", sleep=_sleep)

    r = hc.request("GET", "https://example.test/x", headers={"A": "1"}, request_id="rid1")
    assert r.status_code == 200
    assert slept == [0.1]


def test_http_client_request_timeout_raises_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("t", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    hc = netclient.SdetHttpClient(client)

    with pytest.raises(TimeoutError) as e:
        hc.request("GET", "https://example.test/x")
    assert "request timed out" in str(e.value)


def test_http_client_request_retry_on_429_uses_retry_after(monkeypatch):
    attempts = {"n": 0}
    slept = []

    def _sleep(d: float) -> None:
        slept.append(d)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(
                429, headers={"Retry-After": "7"}, json={"err": "rate"}, request=request
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pol = netclient.RetryPolicy(
        retries=2, retry_on_429=True, backoff_base=0.2, backoff_factor=2.0, backoff_jitter=0.0
    )
    hc = netclient.SdetHttpClient(client, retry=pol, sleep=_sleep)

    r = hc.request("GET", "https://example.test/x")
    assert r.status_code == 200
    assert slept == [7.0]


def test_http_client_request_final_failure_raises_runtime_error_from_request_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pol = netclient.RetryPolicy(retries=2, backoff_base=0.0)
    hc = netclient.SdetHttpClient(client, retry=pol)

    with pytest.raises(RuntimeError) as e:
        hc.request("GET", "https://example.test/x")
    assert "request failed" in str(e.value)
    assert isinstance(e.value.__cause__, httpx.RequestError)


def test_http_client_request_retries_must_be_ge_1():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, request=r)))
    hc = netclient.SdetHttpClient(client)
    with pytest.raises(ValueError):
        hc.request("GET", "https://example.test/x", retry=netclient.RetryPolicy(retries=0))


def test_http_client_request_blocked_by_circuit_breaker():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("request should not run")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    b = netclient.CircuitBreaker(failure_threshold=1, reset_seconds=30.0)
    b.record_failure(0.0)

    hc = netclient.SdetHttpClient(client, breaker=b, clock=lambda: 0.0)

    with pytest.raises(netclient.CircuitOpenError):
        hc.request("GET", "https://example.test/x")


def test_http_client_request_json_non_2xx_raises_http_status_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, content=b"nope", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    hc = netclient.SdetHttpClient(client)

    with pytest.raises(netclient.HttpStatusError) as e:
        hc.get_json_any("https://example.test/x")
    assert e.value.status_code == 418
    assert e.value.body == b"nope"


def test_http_client_pagination_cycle_detected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Link": '<a>; rel="next"'},
            json=[1],
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    hc = netclient.SdetHttpClient(client)

    with pytest.raises(RuntimeError) as e:
        hc.get_json_list_paginated("https://example.test/a", max_pages=3)
    assert "pagination impact" in str(e.value)


def test_backoff_delay_with_jitter_is_deterministic(monkeypatch):
    monkeypatch.setattr(netclient.random, "random", lambda: 1.0)
    d = netclient._backoff_delay(attempt=1, base=1.0, factor=2.0, jitter=0.5)
    assert d == 3.0
