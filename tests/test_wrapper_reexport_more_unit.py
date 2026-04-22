from __future__ import annotations

import importlib
import types

import pytest


@pytest.mark.parametrize(
    ("wrapper_module", "impl_module"),
    [
        ("sdetkit.argv_flags", "sdetkit.core.argv_flags"),
        ("sdetkit.baseline_dispatch", "sdetkit.core.baseline_dispatch"),
        ("sdetkit.release_dispatch", "sdetkit.core.release_dispatch"),
    ],
)
def test_wrapper_module_respects_explicit_all(
    wrapper_module: str, impl_module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    impl = types.ModuleType(impl_module)
    impl.__all__ = ["visible"]
    impl.visible = 123
    impl.hidden = 456

    monkeypatch.setitem(importlib.sys.modules, impl_module, impl)
    monkeypatch.delitem(importlib.sys.modules, wrapper_module, raising=False)

    wrapper = importlib.import_module(wrapper_module)

    assert wrapper.__all__ == ["visible"]
    assert wrapper.visible == 123
    assert not hasattr(wrapper, "hidden")


@pytest.mark.parametrize(
    ("wrapper_module", "impl_module"),
    [
        ("sdetkit.argv_flags", "sdetkit.core.argv_flags"),
        ("sdetkit.baseline_dispatch", "sdetkit.core.baseline_dispatch"),
        ("sdetkit.release_dispatch", "sdetkit.core.release_dispatch"),
    ],
)
def test_wrapper_module_exports_public_names_without_all(
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
