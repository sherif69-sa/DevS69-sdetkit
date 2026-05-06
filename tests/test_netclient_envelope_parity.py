import asyncio

import httpx
import pytest

from sdetkit import apiclient
from sdetkit.netclient import SdetAsyncHttpClient, SdetHttpClient


def test_async_client_envelope_pagination_matches_sync_result():
    sync_calls = []

    def sync_handler(request):
        sync_calls.append(str(request.url))
        if len(sync_calls) == 1:
            return httpx.Response(200, json={"items": [{"id": 1}], "next": "/p2"}, request=request)
        return httpx.Response(200, json={"items": [{"id": 2}], "next": None}, request=request)

    async_calls = []

    async def async_handler(request):
        async_calls.append(str(request.url))
        if len(async_calls) == 1:
            return httpx.Response(200, json={"items": [{"id": 1}], "next": "/p2"}, request=request)
        return httpx.Response(200, json={"items": [{"id": 2}], "next": None}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(sync_handler), base_url="https://example.test"
    ) as raw:
        sync_client = SdetHttpClient(raw)
        sync_result = sync_client.get_json_list_paginated_envelope("/p1")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(async_handler), base_url="https://example.test"
        ) as raw:
            async_client = SdetAsyncHttpClient(raw)
            return await async_client.get_json_list_paginated_envelope("/p1")

    assert asyncio.run(run()) == sync_result == [{"id": 1}, {"id": 2}]
    assert sync_calls == async_calls == ["https://example.test/p1", "https://example.test/p2"]


def test_async_client_envelope_pagination_validates_shape_and_cycle():
    async def run_bad_page():
        async def handler(request):
            return httpx.Response(200, json=[{"id": 1}], request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ) as raw:
            client = SdetAsyncHttpClient(raw)
            return await client.get_json_list_paginated_envelope("/p1")

    with pytest.raises(ValueError, match="expected json object"):
        asyncio.run(run_bad_page())

    async def run_bad_items():
        async def handler(request):
            return httpx.Response(200, json={"items": {"id": 1}, "next": None}, request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ) as raw:
            client = SdetAsyncHttpClient(raw)
            return await client.get_json_list_paginated_envelope("/p1")

    with pytest.raises(ValueError, match="expected json array at key 'items'"):
        asyncio.run(run_bad_items())

    async def run_cycle():
        async def handler(request):
            return httpx.Response(200, json={"items": [1], "next": "/p1"}, request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ) as raw:
            client = SdetAsyncHttpClient(raw)
            return await client.get_json_list_paginated_envelope("/p1")

    with pytest.raises(RuntimeError, match="pagination cycle detected"):
        asyncio.run(run_cycle())


def test_apiclient_exposes_sync_and_async_envelope_helpers():
    assert hasattr(apiclient, "fetch_json_list_paginated_envelope")
    assert hasattr(apiclient, "fetch_json_list_paginated_envelope_async")


def test_apiclient_envelope_helpers_follow_pages():
    sync_calls = []

    def sync_handler(request):
        sync_calls.append(str(request.url))
        if len(sync_calls) == 1:
            return httpx.Response(200, json={"items": ["a"], "next": "/p2"}, request=request)
        return httpx.Response(200, json={"items": ["b"], "next": None}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(sync_handler), base_url="https://example.test"
    ) as raw:
        assert apiclient.fetch_json_list_paginated_envelope(raw, "/p1") == ["a", "b"]

    async_calls = []

    async def async_handler(request):
        async_calls.append(str(request.url))
        if len(async_calls) == 1:
            return httpx.Response(200, json={"items": ["a"], "next": "/p2"}, request=request)
        return httpx.Response(200, json={"items": ["b"], "next": None}, request=request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(async_handler), base_url="https://example.test"
        ) as raw:
            return await apiclient.fetch_json_list_paginated_envelope_async(raw, "/p1")

    assert asyncio.run(run()) == ["a", "b"]
    assert sync_calls == async_calls == ["https://example.test/p1", "https://example.test/p2"]
