from __future__ import annotations

import sys
import types

import sdetkit._toml as toml_compat


def test_toml_compat_uses_tomli_before_python_311(monkeypatch) -> None:
    calls: list[str] = []

    def fake_import_module(name: str) -> object:
        calls.append(name)
        return types.SimpleNamespace(loads=lambda raw: {"raw": raw, "source": name})

    monkeypatch.setattr(toml_compat, "import_module", fake_import_module)
    monkeypatch.setattr(sys, "version_info", (3, 10, 9))

    module = toml_compat._load_toml_module()

    assert calls == ["tomli"]
    assert module.loads("k='v'")["source"] == "tomli"


def test_toml_compat_uses_tomllib_on_python_311_plus(monkeypatch) -> None:
    calls: list[str] = []

    def fake_import_module(name: str) -> object:
        calls.append(name)
        return types.SimpleNamespace(loads=lambda raw: {"raw": raw, "source": name})

    monkeypatch.setattr(toml_compat, "import_module", fake_import_module)
    monkeypatch.setattr(sys, "version_info", (3, 11, 0))

    module = toml_compat._load_toml_module()

    assert calls == ["tomllib"]
    assert module.loads("k='v'")["source"] == "tomllib"
