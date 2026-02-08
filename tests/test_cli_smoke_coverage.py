import importlib
import sys
import time
from typing import Any

import httpx
import pytest


def _run_cli(argv: list[str]) -> int:
    mod = importlib.import_module("sdetkit.cli")
    fn = getattr(mod, "main", None) or getattr(mod, "run", None) or getattr(mod, "cli", None)
    if fn is None or not callable(fn):
        pytest.skip("no cli runner found in sdetkit.cli")

    old_argv = sys.argv[:]
    try:
        sys.argv = ["sdetkit", *argv]
        try:
            res = fn()  # type: ignore[misc]
        except SystemExit as e:
            code = 0 if e.code is None else int(e.code) if isinstance(e.code, int) else 0
            return code
        if isinstance(res, int):
            return res
        return 0
    finally:
        sys.argv = old_argv


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)


@pytest.fixture()
def _mock_httpx(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    counters: dict[str, int] = {"server_error_once": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/ok":
            return httpx.Response(200, json={"ok": True}, request=request)

        if path == "/server-error-once":
            counters["server_error_once"] += 1
            if counters["server_error_once"] == 1:
                return httpx.Response(500, json={"error": "boom"}, request=request)
            return httpx.Response(200, json={"ok": True, "retried": True}, request=request)

        if path == "/bad-json":
            return httpx.Response(
                200,
                content=b"not-json",
                headers={"content-type": "application/json"},
                request=request,
            )

        if path == "/timeout":
            raise httpx.ReadTimeout("timeout", request=request)

        if path == "/not-found":
            return httpx.Response(404, json={"detail": "nope"}, request=request)

        return httpx.Response(200, json={"path": path}, request=request)

    transport = httpx.MockTransport(handler)

    class PatchedClient(httpx.Client):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("transport", transport)
            kwargs.setdefault("base_url", "https://example.invalid")
            super().__init__(*args, **kwargs)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("transport", transport)
            kwargs.setdefault("base_url", "https://example.invalid")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", PatchedClient)
    monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)

    return counters


def test_main_module_runs(_mock_httpx: dict[str, int]) -> None:
    sys.modules.pop("sdetkit.__main__", None)
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sdetkit", "--help"]
        try:
            importlib.import_module("sdetkit.__main__")
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv


def test_entrypoints_wrappers_do_not_crash(_mock_httpx: dict[str, int]) -> None:
    eps = importlib.import_module("sdetkit._entrypoints")

    old_argv = sys.argv[:]
    try:
        sys.argv = ["kvcli", "--help"]
        try:
            eps.kvcli()
        except SystemExit:
            pass

        sys.argv = ["apigetcli", "--help"]
        try:
            eps.apigetcli()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv


def test_cli_apiget_exercises_http_stack(_mock_httpx: dict[str, int]) -> None:
    _run_cli(["--help"])

    _run_cli(["apiget", "https://example.invalid/ok"])
    _run_cli(["apiget", "https://example.invalid/server-error-once"])
    _run_cli(["apiget", "https://example.invalid/not-found"])
    _run_cli(["apiget", "https://example.invalid/bad-json"])
    _run_cli(["apiget", "https://example.invalid/timeout"])

    assert _mock_httpx["server_error_once"] >= 1
