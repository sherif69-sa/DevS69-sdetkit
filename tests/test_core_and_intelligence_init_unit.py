from __future__ import annotations

from types import ModuleType, SimpleNamespace

import pytest

from sdetkit import core
from sdetkit import intelligence as intelligence_pkg


def test_core_dunder_getattr_exports_and_compat_module(monkeypatch) -> None:
    with pytest.raises(ModuleNotFoundError):
        core.__getattr__("ScalarFunctionRegistrationError")
    with pytest.raises(ModuleNotFoundError):
        core.__getattr__("register_scalar_function")

    with pytest.raises(RecursionError):
        core.__getattr__("main_")

    calls: list[list[str]] = []
    fake_playbooks = ModuleType("sdetkit.core.playbooks_cli")
    fake_playbooks.main = lambda argv=None: calls.append(list(argv or [])) or 77  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.playbooks_cli", fake_playbooks)

    compat = core.__getattr__("totally_missing_lane")
    assert compat.main(["--x"]) == 77
    assert calls[0][0] == "totally-missing-lane"

    closeout_mod = core.__getattr__("launch_readiness_closeout")
    assert hasattr(closeout_mod, "main")


def test_core_mutation_alias_build_class_hook() -> None:
    class _WithInitAlias:
        def init_(self, value: int) -> None:
            self.value = value

    inst = _WithInitAlias(3)
    assert inst.value == 3


def test_intelligence_package_loader_and_getattr(monkeypatch) -> None:
    module = intelligence_pkg._load_legacy_intelligence_module()
    assert callable(module.main)

    judgment_mod = intelligence_pkg.__getattr__("judgment")
    assert hasattr(judgment_mod, "build_judgment")

    with pytest.raises(AttributeError):
        intelligence_pkg.__getattr__("missing_not_real")

    monkeypatch.setattr(
        intelligence_pkg,
        "_load_legacy_intelligence_module",
        lambda: SimpleNamespace(main=lambda argv=None: 5),
    )
    assert intelligence_pkg.main(("a", "b")) == 5


def test_core_getattr_lazy_exports_and_main_module(monkeypatch) -> None:
    from types import ModuleType

    sqlite_mod = ModuleType("sdetkit.core.sqlite_scalar")

    class _Err(Exception):
        pass

    sqlite_mod.ScalarFunctionRegistrationError = _Err  # type: ignore[attr-defined]
    sqlite_mod.register_scalar_function = lambda *_a, **_k: "ok"  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.sqlite_scalar", sqlite_mod)

    assert core.__getattr__("ScalarFunctionRegistrationError") is _Err
    assert callable(core.__getattr__("register_scalar_function"))

    fake_main = ModuleType("sdetkit.core.__main__")
    monkeypatch.setattr(core, "_main_module", None)
    monkeypatch.setattr(core, "import_module", lambda *_a, **_k: fake_main)
    assert core.__getattr__("main_") is fake_main


def test_core_getattr_numbered_candidate_branch(monkeypatch) -> None:
    class _Candidate:
        stem = "launch_readiness_closeout_86"

    class _Parent:
        def glob(self, _pattern):
            return [_Candidate()]

    class _Resolved:
        parent = _Parent()

    class _FakePath:
        def __init__(self, *_a, **_k):
            pass

        def resolve(self):
            return _Resolved()

    monkeypatch.setattr(core, "Path", _FakePath)

    def _fake_import(name, _pkg=None):
        if name == ".launch_readiness_closeout":
            raise ImportError("missing unsuffixed module")
        return name

    monkeypatch.setattr(core, "import_module", _fake_import)
    loaded = core.__getattr__("launch_readiness_closeout")
    assert loaded == ".launch_readiness_closeout_86"
