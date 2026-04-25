from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

import sdetkit.netclient as netclient
from sdetkit.netclient import CircuitBreaker, HttpStatusError, RetryPolicy, SdetHttpClient


def test_http_status_error_uses_response_url_when_request_url_fails() -> None:
    class BadReq:
        @property
        def url(self) -> str:
            raise RuntimeError("nope")

    class FakeResp:
        status_code = 418
        request = BadReq()
        url = "https://example.test/fallback"
        content = b"body"

    e = HttpStatusError("x", response=FakeResp())
    assert e.url == "https://example.test/fallback"
    assert e.status_code == 418
    assert e.body == b"body"


def test_circuit_breaker_half_open_can_only_be_used_once() -> None:
    b = CircuitBreaker(failure_threshold=1, reset_seconds=0.0)
    b._opened_at = 0.0

    b.allow(1.0)
    with pytest.raises(netclient.CircuitOpenError):
        b.allow(2.0)


def test_link_next_url_skips_bad_parts_and_returns_next() -> None:
    req = httpx.Request("GET", "https://example.test/base")
    r = httpx.Response(
        200,
        request=req,
        headers={
            "Link": ",".join(
                [
                    "<https://example.test/skip>; title=x",
                    "nope",
                    "https://example.test/bad; rel=next",
                    '<page2>; rel="next"',
                ]
            )
        },
    )
    assert netclient._link_next_url(r) == "https://example.test/page2"


def test_link_next_url_returns_none_when_no_next() -> None:
    req = httpx.Request("GET", "https://example.test/base")
    r = httpx.Response(200, request=req, headers={"Link": '<page2>; rel="prev"'})
    assert netclient._link_next_url(r) is None


def test_link_next_url_treats_rel_parameter_name_and_value_case_insensitively() -> None:
    req = httpx.Request("GET", "https://example.test/base")
    r = httpx.Response(200, request=req, headers={"Link": "<page2>; REL=NEXT"})
    assert netclient._link_next_url(r) == "https://example.test/page2"


@dataclass
class SpyBreaker:
    allow_calls: int = 0
    failure_calls: int = 0
    success_calls: int = 0

    def allow(self, now: float) -> None:
        self.allow_calls += 1

    def record_failure(self, now: float) -> None:
        self.failure_calls += 1

    def record_success(self) -> None:
        self.success_calls += 1


def test_request_timeout_records_failure_and_raises_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("t", request=request)

    spy = SpyBreaker()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client, breaker=spy, clock=lambda: 1.0)
        with pytest.raises(TimeoutError, match="timed out"):
            c.request("GET", "https://example.test/t", retry=RetryPolicy(retries=1))

    assert spy.allow_calls == 1
    assert spy.failure_calls == 1
    assert spy.success_calls == 0


def test_request_error_then_success_records_failure_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("c", request=request)
        return httpx.Response(200, request=request)

    spy = SpyBreaker()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client, breaker=spy, clock=lambda: 1.0)
        r = c.request(
            "GET",
            "https://example.test/r",
            retry=RetryPolicy(retries=2, backoff_base=0.0),
        )
        assert r.status_code == 200

    assert spy.allow_calls == 2
    assert spy.failure_calls == 1
    assert spy.success_calls == 1


def test_request_429_then_success_records_failure_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, request=request)
        return httpx.Response(200, request=request)

    spy = SpyBreaker()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client, breaker=spy, clock=lambda: 1.0)
        r = c.request(
            "GET",
            "https://example.test/rl",
            retry=RetryPolicy(retries=2, retry_on_429=True, backoff_base=0.0),
        )
        assert r.status_code == 200

    assert spy.allow_calls == 2
    assert spy.failure_calls == 1
    assert spy.success_calls == 1


def test_request_retries_must_be_ge_1() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, request=r))
    ) as client:
        c = SdetHttpClient(client)
        with pytest.raises(ValueError, match="retries must be >= 1"):
            c.request("GET", "https://example.test/x", retry=RetryPolicy(retries=0))


def test_get_json_list_rejects_non_array_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"x": 1}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(ValueError, match="expected json array"):
            c.get_json_list("https://example.test/list")


def test_get_json_list_paginated_max_pages_and_limit_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[1],
            headers={"Link": '<next>; rel="next"'},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            c.get_json_list_paginated("https://example.test/p", max_pages=0)

        with pytest.raises(RuntimeError, match="pagination limit exceeded"):
            c.get_json_list_paginated("https://example.test/p", max_pages=1)


def test_get_json_list_paginated_detects_cycle_back_to_origin_without_extra_fetch() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            json=[1],
            headers={"Link": '<https://example.test/p>; rel="next"'},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(RuntimeError, match="pagination impact"):
            c.get_json_list_paginated("https://example.test/p")

    assert calls["n"] == 1


def test_get_json_list_paginated_envelope_validation_and_limit_exceeded() -> None:
    def handler_bad_obj(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1], request=request)

    with httpx.Client(transport=httpx.MockTransport(handler_bad_obj)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            c.get_json_list_paginated_envelope("https://example.test/e", max_pages=0)
        with pytest.raises(ValueError, match="items_key must not be empty"):
            c.get_json_list_paginated_envelope("https://example.test/e", items_key="  ")
        with pytest.raises(ValueError, match="next_key must not be empty"):
            c.get_json_list_paginated_envelope("https://example.test/e", next_key="  ")
        with pytest.raises(ValueError, match="expected json object"):
            c.get_json_list_paginated_envelope("https://example.test/e")

    def handler_bad_next_type(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [1], "next": 1}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler_bad_next_type)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(ValueError, match="expected string or null"):
            c.get_json_list_paginated_envelope("https://example.test/e")

    def handler_limit(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [1], "next": "next"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler_limit)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(RuntimeError, match="pagination limit exceeded"):
            c.get_json_list_paginated_envelope("https://example.test/e", max_pages=1)


def test_get_json_any_rejects_scalar_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=1, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        c = SdetHttpClient(client)
        with pytest.raises(ValueError, match="expected json object or array"):
            c.get_json_any("https://example.test/a")
