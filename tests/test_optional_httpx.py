from __future__ import annotations

import types

from sdetkit import optional_httpx


def test_load_httpx_returns_fallback_when_module_missing(monkeypatch) -> None:
    monkeypatch.setattr(optional_httpx.importlib.util, "find_spec", lambda _name: None)

    module = optional_httpx.load_httpx(feature="sdetkit apiget")
    assert hasattr(module, "Client")
    assert hasattr(module, "HTTPTransport")
    try:
        module.Client()
        raise AssertionError("expected fallback Client() to raise ModuleNotFoundError")
    except ModuleNotFoundError as exc:
        assert "sdetkit apiget" in str(exc)

    try:
        module.HTTPTransport()
        raise AssertionError("expected fallback HTTPTransport() to raise ModuleNotFoundError")
    except ModuleNotFoundError as exc:
        assert "optional network dependencies" in str(exc)


def test_load_httpx_imports_module_when_available(monkeypatch) -> None:
    expected = types.SimpleNamespace(__name__="httpx")
    monkeypatch.setattr(optional_httpx.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(optional_httpx.importlib, "import_module", lambda _name: expected)

    loaded = optional_httpx.load_httpx(feature="sdetkit apiget")
    assert loaded is expected
