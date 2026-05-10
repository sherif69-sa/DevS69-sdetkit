from __future__ import annotations

import importlib
import types

import pytest


def test_legacy_workflow_wrapper_uses_impl_all(monkeypatch: pytest.MonkeyPatch) -> None:
    impl = types.ModuleType("sdetkit.core._legacy_workflow")
    impl.__all__ = ["main"]
    impl.main = lambda: 5
    impl.hidden = "skip"

    monkeypatch.setitem(importlib.sys.modules, "sdetkit.core._legacy_workflow", impl)
    monkeypatch.delitem(importlib.sys.modules, "sdetkit._legacy_workflow", raising=False)

    wrapper = importlib.import_module("sdetkit._legacy_workflow")

    assert wrapper.__all__ == ["main"]
    assert wrapper.main() == 5
    assert not hasattr(wrapper, "hidden")


def test_legacy_workflow_wrapper_builds_all_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    impl = types.ModuleType("sdetkit.core._legacy_workflow")
    impl.alpha = "a"
    impl.beta = "b"
    impl.__private = "secret"

    monkeypatch.setitem(importlib.sys.modules, "sdetkit.core._legacy_workflow", impl)
    monkeypatch.delitem(importlib.sys.modules, "sdetkit._legacy_workflow", raising=False)

    wrapper = importlib.import_module("sdetkit._legacy_workflow")

    assert "alpha" in wrapper.__all__
    assert "beta" in wrapper.__all__
    assert wrapper.alpha == "a"
    assert wrapper.beta == "b"
