import httpx
import pytest

from sdetkit.apiclient import fetch_json_list


def test_fetch_json_list_success_and_trace_header():
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-Request-ID"))
        return httpx.Response(200, json=[1, 2, 3])

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="https://example.test") as client:
        out = fetch_json_list(client, "/x", trace_header="X-Request-ID", request_id="abc")

    assert out == [1, 2, 3]
    assert seen == ["abc"]


def test_fetch_json_list_rejects_non_list_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"x": 1})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="https://example.test") as client:
        with pytest.raises(ValueError):
            fetch_json_list(client, "/x")
