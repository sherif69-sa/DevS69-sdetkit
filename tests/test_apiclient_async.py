import httpx
import pytest

from sdetkit.apiclient import fetch_json_dict_async


@pytest.mark.asyncio
async def test_fetch_json_dict_async_ok():
    def handler(request):
        return httpx.Response(200, json={"a": "1"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        out = await fetch_json_dict_async(client, "/kv")
    assert out == {"a": "1"}


@pytest.mark.asyncio
async def test_fetch_json_dict_async_timeout_maps_to_timeouterror():
    def handler(request):
        raise httpx.ReadTimeout("boom", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        with pytest.raises(TimeoutError):
            await fetch_json_dict_async(client, "/kv")


@pytest.mark.asyncio
async def test_fetch_json_dict_async_network_error_maps_to_runtimeerror():
    def handler(request):
        raise httpx.ConnectError("no network", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        with pytest.raises(RuntimeError):
            await fetch_json_dict_async(client, "/kv")


@pytest.mark.asyncio
async def test_fetch_json_dict_async_concurrent_calls_are_stable():
    def handler(request):
        return httpx.Response(200, json={"ok": "1"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        import asyncio

        outs = await asyncio.gather(*[fetch_json_dict_async(client, "/kv") for _ in range(50)])
    assert outs == [{"ok": "1"}] * 50


@pytest.mark.asyncio
async def test_fetch_json_dict_async_cancellation_is_not_wrapped():
    import asyncio

    gate = asyncio.Event()

    class GateTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await gate.wait()
            return httpx.Response(200, json={"ok": "1"}, request=request)

    client = httpx.AsyncClient(transport=GateTransport(), base_url="https://example.test")
    async with client:
        tasks = [asyncio.create_task(fetch_json_dict_async(client, "/kv")) for _ in range(10)]
        await asyncio.sleep(0)

        for t in tasks[:5]:
            t.cancel()

        gate.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)

    cancelled = sum(isinstance(r, asyncio.CancelledError) for r in results)
    ok = [r for r in results if isinstance(r, dict)]

    assert cancelled == 5
    assert ok == [{"ok": "1"}] * 5


@pytest.mark.asyncio
async def test_fetch_json_dict_async_retries_on_requesterror_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("no network", request=request)
        return httpx.Response(200, json={"ok": "1"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        out = await fetch_json_dict_async(client, "/kv", retries=3)

    assert out == {"ok": "1"}
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_fetch_json_dict_async_retries_exhausted_raises_runtimeerror():
    def handler(request):
        raise httpx.ConnectError("no network", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        with pytest.raises(RuntimeError):
            await fetch_json_dict_async(client, "/kv", retries=2)


@pytest.mark.asyncio
async def test_fetch_json_dict_async_retries_must_be_ge_1():
    def handler(request):
        return httpx.Response(200, json={"ok": "1"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        with pytest.raises(ValueError):
            await fetch_json_dict_async(client, "/kv", retries=0)


@pytest.mark.asyncio
async def test_fetch_json_dict_async_non_2xx_does_not_retry():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, json={"err": "x"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        with pytest.raises(RuntimeError):
            await fetch_json_dict_async(client, "/kv", retries=5)

    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_fetch_json_dict_async_non_object_json_raises_valueerror():
    def handler(request):
        return httpx.Response(200, json=[1, 2, 3])

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    async with client:
        with pytest.raises(ValueError):
            await fetch_json_dict_async(client, "/kv")


def test_fetch_json_dict_async_status_code_edges_mutmut():
    import asyncio
    import pytest
    from sdetkit.apiclient import fetch_json_dict_async

    class Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.json_calls = 0

        def json(self):
            self.json_calls += 1
            return self._payload

    class Client:
        def __init__(self, resp):
            self.resp = resp
            self.calls = 0

        async def get(self, *a, **k):
            self.calls += 1
            return self.resp

    ok = Resp(200, {"ok": 1})
    c = Client(ok)
    assert asyncio.run(fetch_json_dict_async(c, "https://example.invalid/x", retries=1)) == {
        "ok": 1
    }
    assert c.calls == 1
    assert ok.json_calls == 1

    ok2 = Resp(299, {"ok": 1})
    assert asyncio.run(
        fetch_json_dict_async(Client(ok2), "https://example.invalid/x", retries=1)
    ) == {"ok": 1}

    with pytest.raises(RuntimeError):
        asyncio.run(
            fetch_json_dict_async(
                Client(Resp(199, {"ok": 1})), "https://example.invalid/x", retries=1
            )
        )

    with pytest.raises(RuntimeError):
        asyncio.run(
            fetch_json_dict_async(
                Client(Resp(300, {"ok": 1})), "https://example.invalid/x", retries=1
            )
        )


def test_fetch_json_dict_async_retries_stop_after_success_mutmut():
    import asyncio
    import httpx
    from sdetkit.apiclient import fetch_json_dict_async

    class Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class Client:
        def __init__(self, actions):
            self.actions = list(actions)
            self.calls = 0

        async def get(self, *a, **k):
            self.calls += 1
            act = self.actions.pop(0)
            if isinstance(act, BaseException):
                raise act
            return act

    req = httpx.Request("GET", "https://example.invalid/x")
    c = Client([httpx.RequestError("boom", request=req), Resp(200, {"ok": 1})])

    assert asyncio.run(fetch_json_dict_async(c, "https://example.invalid/x", retries=3)) == {
        "ok": 1
    }
    assert c.calls == 2


def test_fetch_json_dict_async_retries_exhausted_call_count_mutmut():
    import asyncio
    import httpx
    import pytest
    from sdetkit.apiclient import fetch_json_dict_async

    class Client:
        def __init__(self, exc):
            self.exc = exc
            self.calls = 0

        async def get(self, *a, **k):
            self.calls += 1
            raise self.exc

    req = httpx.Request("GET", "https://example.invalid/x")
    c = Client(httpx.RequestError("boom", request=req))

    with pytest.raises(RuntimeError):
        asyncio.run(fetch_json_dict_async(c, "https://example.invalid/x", retries=3))
    assert c.calls == 3


def test_fetch_json_dict_async_timeout_is_timeout_error_mutmut():
    import asyncio
    import httpx
    import pytest
    from sdetkit.apiclient import fetch_json_dict_async

    class Client:
        def __init__(self, exc):
            self.exc = exc
            self.calls = 0

        async def get(self, *a, **k):
            self.calls += 1
            raise self.exc

    req = httpx.Request("GET", "https://example.invalid/x")
    c = Client(httpx.TimeoutException("timeout", request=req))

    with pytest.raises(TimeoutError) as ei:
        asyncio.run(fetch_json_dict_async(c, "https://example.invalid/x", retries=5))
    assert c.calls == 1
    assert isinstance(ei.value.__cause__, httpx.TimeoutException)
