import httpx
import pytest

from sdetkit.apiclient import fetch_json_dict


def test_fetch_json_dict_ok():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/kv"
        return httpx.Response(200, json={"a": "1", "b": "two"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    out = fetch_json_dict(client, "/kv")
    assert out == {"a": "1", "b": "two"}


def test_fetch_json_dict_non_2xx_raises():
    def handler(request):
        return httpx.Response(404, json={"detail": "nope"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    with pytest.raises(RuntimeError):
        fetch_json_dict(client, "/kv")


def test_fetch_json_dict_invalid_json_shape_raises_value_error():
    def handler(request):
        return httpx.Response(200, json=["not", "a", "dict"])

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    with pytest.raises(ValueError):
        fetch_json_dict(client, "/kv")


def test_fetch_json_dict_timeout_maps_to_timeouterror():
    def handler(request):
        raise httpx.ReadTimeout("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    with pytest.raises(TimeoutError):
        fetch_json_dict(client, "/kv")


def test_fetch_json_dict_accepts_path_without_leading_slash():
    def handler(request):
        assert request.url.path == "/kv"
        return httpx.Response(200, json={"ok": "1"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    out = fetch_json_dict(client, "kv")
    assert out == {"ok": "1"}


def test_fetch_json_dict_network_error_maps_to_runtimeerror():
    def handler(request):
        raise httpx.ConnectError("no network", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    with pytest.raises(RuntimeError):
        fetch_json_dict(client, "/kv")


def test_fetch_json_dict_retries_on_requesterror_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("no network", request=request)
        return httpx.Response(200, json={"ok": "1"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    out = fetch_json_dict(client, "/kv", retries=3)
    assert out == {"ok": "1"}
    assert calls["n"] == 3


def test_fetch_json_dict_non_2xx_does_not_retry():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, json={"err": "x"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    with pytest.raises(RuntimeError):
        fetch_json_dict(client, "/kv", retries=5)

    assert calls["n"] == 1


def test_fetch_json_dict_retries_must_be_ge_1_sync():
    import httpx
    import pytest

    from sdetkit.apiclient import fetch_json_dict

    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": "1"}))
    )
    with pytest.raises(ValueError):
        fetch_json_dict(client, "/kv", retries=0)


def test_fetch_json_dict_status_code_edges_mutmut():
    import pytest

    from sdetkit.apiclient import fetch_json_dict

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

        def get(self, *a, **k):
            self.calls += 1
            return self.resp

    ok = Resp(200, {"ok": 1})
    c = Client(ok)
    assert fetch_json_dict(c, "https://example.invalid/x", retries=1) == {"ok": 1}
    assert c.calls == 1
    assert ok.json_calls == 1

    ok2 = Resp(299, {"ok": 1})
    assert fetch_json_dict(Client(ok2), "https://example.invalid/x", retries=1) == {"ok": 1}

    with pytest.raises(RuntimeError):
        fetch_json_dict(Client(Resp(199, {"ok": 1})), "https://example.invalid/x", retries=1)

    with pytest.raises(RuntimeError):
        fetch_json_dict(Client(Resp(300, {"ok": 1})), "https://example.invalid/x", retries=1)


def test_fetch_json_dict_retries_stop_after_success_mutmut():
    import httpx

    from sdetkit.apiclient import fetch_json_dict

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

        def get(self, *a, **k):
            self.calls += 1
            act = self.actions.pop(0)
            if isinstance(act, BaseException):
                raise act
            return act

    req = httpx.Request("GET", "https://example.invalid/x")
    c = Client([httpx.RequestError("boom", request=req), Resp(200, {"ok": 1})])

    assert fetch_json_dict(c, "https://example.invalid/x", retries=3) == {"ok": 1}
    assert c.calls == 2


def test_fetch_json_dict_retries_exhausted_call_count_mutmut():
    import httpx
    import pytest

    from sdetkit.apiclient import fetch_json_dict

    class Client:
        def __init__(self, exc):
            self.exc = exc
            self.calls = 0

        def get(self, *a, **k):
            self.calls += 1
            raise self.exc

    req = httpx.Request("GET", "https://example.invalid/x")
    c = Client(httpx.RequestError("boom", request=req))

    with pytest.raises(RuntimeError):
        fetch_json_dict(c, "https://example.invalid/x", retries=3)
    assert c.calls == 3


def test_fetch_json_dict_timeout_is_timeout_error_mutmut():
    import httpx
    import pytest

    from sdetkit.apiclient import fetch_json_dict

    class Client:
        def __init__(self, exc):
            self.exc = exc
            self.calls = 0

        def get(self, *a, **k):
            self.calls += 1
            raise self.exc

    req = httpx.Request("GET", "https://example.invalid/x")
    c = Client(httpx.TimeoutException("timeout", request=req))

    with pytest.raises(TimeoutError) as ei:
        fetch_json_dict(c, "https://example.invalid/x", retries=5)
    assert c.calls == 1
    assert isinstance(ei.value.__cause__, httpx.TimeoutException)
