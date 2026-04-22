from __future__ import annotations

import importlib
import types

import pytest


@pytest.mark.parametrize(
    ("wrapper_module", "impl_module"),
    [
        ("sdetkit.cli_shortcuts", "sdetkit.cli.cli_shortcuts"),
        ("sdetkit.serve_forwarding", "sdetkit.cli.serve_forwarding"),
    ],
)
def test_cli_wrapper_reexport_respects_all(
    wrapper_module: str, impl_module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    impl = types.ModuleType(impl_module)
    impl.__all__ = ["public_api"]
    impl.public_api = lambda: "ok"
    impl.not_public = lambda: "nope"

    monkeypatch.setitem(importlib.sys.modules, impl_module, impl)
    monkeypatch.delitem(importlib.sys.modules, wrapper_module, raising=False)

    wrapper = importlib.import_module(wrapper_module)

    assert wrapper.__all__ == ["public_api"]
    assert wrapper.public_api() == "ok"
    assert not hasattr(wrapper, "not_public")


@pytest.mark.parametrize(
    ("wrapper_module", "impl_module"),
    [
        ("sdetkit.cli_shortcuts", "sdetkit.cli.cli_shortcuts"),
        ("sdetkit.serve_forwarding", "sdetkit.cli.serve_forwarding"),
    ],
)
def test_cli_wrapper_reexport_uses_public_names_without_all(
    wrapper_module: str, impl_module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    impl = types.ModuleType(impl_module)
    impl.alpha = "a"
    impl.beta = "b"

    monkeypatch.setitem(importlib.sys.modules, impl_module, impl)
    monkeypatch.delitem(importlib.sys.modules, wrapper_module, raising=False)

    wrapper = importlib.import_module(wrapper_module)

    assert "alpha" in wrapper.__all__
    assert "beta" in wrapper.__all__
    assert wrapper.alpha == "a"
    assert wrapper.beta == "b"
