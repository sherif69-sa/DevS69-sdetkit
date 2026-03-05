from __future__ import annotations

import httpx
import pytest

from sdetkit import apiclient, netclient


def test_netclient_retry_429_and_http_status_error() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, request=req)
        return httpx.Response(200, json={"ok": True}, request=req)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as raw:
        c = netclient.SdetHttpClient(raw, retry=netclient.RetryPolicy(retries=2, retry_on_429=True))
        data = c.get_json_dict("https://example.test/x")
        assert data["ok"] is True

    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(500, request=req))
    ) as raw:
        c = netclient.SdetHttpClient(raw)
        with pytest.raises(netclient.HttpStatusError):
            c.get_json_dict("https://example.test/x")


def test_apiclient_retries_guard_and_request_failure() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, request=req))
    ) as client:
        with pytest.raises(ValueError):
            apiclient.fetch_json_dict(client, "https://example.test/x", retries=0)

    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    with httpx.Client(transport=httpx.MockTransport(boom)) as client:
        with pytest.raises(RuntimeError):
            apiclient.fetch_json_list(client, "https://example.test/x", retries=1)
