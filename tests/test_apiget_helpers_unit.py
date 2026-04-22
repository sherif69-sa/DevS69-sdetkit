from __future__ import annotations

import argparse

import pytest

from sdetkit import apiget


class _BrokenHeadersClient:
    @property
    def headers(self):
        raise RuntimeError("boom")


class _ItemsOnlyMapping:
    def items(self):
        return [("X-Trace", "abc"), ("Accept", "application/json")]


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 201
        self.headers = {"B": "2", "a": "1"}


def test_validate_header_text_rejects_controls() -> None:
    assert apiget._validate_header_text("ok", field="h") == "ok"
    with pytest.raises(ValueError, match="invalid h"):
        apiget._validate_header_text("bad\n", field="h")


def test_merged_headers_handles_broken_client_and_items_only_extra() -> None:
    merged = apiget._merged_headers(_BrokenHeadersClient(), _ItemsOnlyMapping(), debug=False)
    assert merged["X-Trace"] == "abc"
    assert merged["Accept"] == "application/json"


def test_verbose_request_filters_default_user_agent_and_prints_custom(capsys) -> None:
    apiget._verbose_request(
        "GET",
        "https://example.test/items?token=secret",
        {
            "User-Agent": "python-httpx/0.27.0",
            "X-Client": "sdetkit",
            "Authorization": "Bearer secret-token",
        },
        keep=None,
        redact=True,
    )
    err = capsys.readouterr().err
    assert "http request: GET" in err
    assert "http request curl:" in err
    assert "python-httpx" not in err
    assert "x-client" in err.lower()


def test_verbose_response_emits_sorted_headers(capsys) -> None:
    apiget._verbose_response(_FakeResponse(), redact=False)
    err = capsys.readouterr().err.splitlines()
    assert err[0] == "http response: 201"
    assert err[1].startswith("http response header: a:")
    assert err[2].startswith("http response header: B:")


def test_add_apiget_args_sets_redirect_and_redact_defaults() -> None:
    p = argparse.ArgumentParser()
    apiget._add_apiget_args(p)
    ns = p.parse_args(["https://example.test"])
    assert ns.follow_redirects is False
    assert ns.redact is True
    assert ns.method == "GET"
