from __future__ import annotations

import importlib
import types

import pytest


@pytest.mark.parametrize(
    ("wrapper_module", "impl_module"),
    [
        ("sdetkit.apiget_dispatch", "sdetkit.core.apiget_dispatch"),
        ("sdetkit.core_preparse_dispatch", "sdetkit.core.core_preparse_dispatch"),
    ],
)
def test_reexport_wrapper_respects_impl_all(
    wrapper_module: str, impl_module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    impl = types.ModuleType(impl_module)
    impl.__all__ = ["exported"]
    impl.exported = object()
    impl.not_exported = object()

    monkeypatch.setitem(importlib.sys.modules, impl_module, impl)
    monkeypatch.delitem(importlib.sys.modules, wrapper_module, raising=False)

    wrapper = importlib.import_module(wrapper_module)

    assert wrapper.__all__ == ["exported"]
    assert wrapper.exported is impl.exported
    assert not hasattr(wrapper, "not_exported")


@pytest.mark.parametrize(
    ("wrapper_module", "impl_module"),
    [
        ("sdetkit.apiget_dispatch", "sdetkit.core.apiget_dispatch"),
        ("sdetkit.core_preparse_dispatch", "sdetkit.core.core_preparse_dispatch"),
    ],
)
def test_reexport_wrapper_falls_back_to_public_names(
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
