import httpx
import pytest

from sdetkit.apiclient import fetch_json_dict, fetch_json_dict_async


def test_fetch_json_dict_retries_guard_message():
    client = httpx.Client(base_url="https://example.test")
    with pytest.raises(ValueError, match=r"^retries must be >= 1$"):
        fetch_json_dict(client, "/x", retries=0)


def test_fetch_json_dict_default_does_not_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))

    with pytest.raises(RuntimeError, match=r"^request failed$"):
        fetch_json_dict(client, "/x")

    assert calls == 1


def test_fetch_json_dict_timeout_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))

    with pytest.raises(TimeoutError, match=r"^request timed out$"):
        fetch_json_dict(client, "/x", retries=3)


def test_fetch_json_dict_non_2xx_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, content=b"nope")

    client = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))

    with pytest.raises(RuntimeError, match=r"^non-2xx response$"):
        fetch_json_dict(client, "/x")


def test_fetch_json_dict_expected_object_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    client = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))

    with pytest.raises(ValueError, match=r"^expected json object$"):
        fetch_json_dict(client, "/x")


@pytest.mark.anyio
async def test_fetch_json_dict_async_retries_guard_message():
    client = httpx.AsyncClient(base_url="https://example.test")
    try:
        with pytest.raises(ValueError, match=r"^retries must be >= 1$"):
            await fetch_json_dict_async(client, "/x", retries=0)
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fetch_json_dict_async_default_does_not_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("boom", request=request)

    client = httpx.AsyncClient(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(RuntimeError, match=r"^request failed$"):
            await fetch_json_dict_async(client, "/x")
    finally:
        await client.aclose()

    assert calls == 1


@pytest.mark.anyio
async def test_fetch_json_dict_async_timeout_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = httpx.AsyncClient(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(TimeoutError, match=r"^request timed out$"):
            await fetch_json_dict_async(client, "/x", retries=3)
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fetch_json_dict_async_non_2xx_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, content=b"nope")

    client = httpx.AsyncClient(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(RuntimeError, match=r"^non-2xx response$"):
            await fetch_json_dict_async(client, "/x")
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_fetch_json_dict_async_expected_object_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    client = httpx.AsyncClient(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(ValueError, match=r"^expected json object$"):
            await fetch_json_dict_async(client, "/x")
    finally:
        await client.aclose()
