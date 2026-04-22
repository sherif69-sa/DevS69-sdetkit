from __future__ import annotations

import pytest

import sdetkit


def test_package_getattr_re_raises_nested_module_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_import(module_name: str):
        raise ModuleNotFoundError("nested import failed", name="some_dependency")

    monkeypatch.setattr(sdetkit.importlib, "import_module", _fake_import)
    with pytest.raises(ModuleNotFoundError) as excinfo:
        sdetkit.__getattr__("anything")
    assert excinfo.value.name == "some_dependency"


def test_package_getattr_raises_attribute_error_after_all_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = set()

    def _fake_import(module_name: str):
        missing.add(module_name)
        raise ModuleNotFoundError(f"No module named {module_name!r}", name=module_name)

    monkeypatch.setattr(sdetkit.importlib, "import_module", _fake_import)
    with pytest.raises(AttributeError):
        sdetkit.__getattr__("definitely_missing_module")

    assert "sdetkit.definitely_missing_module" in missing
    assert "sdetkit.core.definitely_missing_module" in missing


def test_package_getattr_caches_loaded_module_for_future_attribute_access(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    marker = object()

    def _fake_import(module_name: str):
        calls.append(module_name)
        return marker

    monkeypatch.delattr(sdetkit, "playbooks_cli", raising=False)
    monkeypatch.setattr(sdetkit.importlib, "import_module", _fake_import)

    loaded = sdetkit.playbooks_cli
    cached = sdetkit.playbooks_cli

    assert loaded is marker
    assert cached is marker
    assert calls == ["sdetkit.cli.playbooks_cli"]
