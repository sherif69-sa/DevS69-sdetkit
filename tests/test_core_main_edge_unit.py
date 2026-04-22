from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_core_main(monkeypatch):
    src_root = Path(__file__).resolve().parents[1] / "src" / "sdetkit" / "core"
    core_pkg = ModuleType("sdetkit.core")
    core_pkg.__path__ = [str(src_root)]  # type: ignore[attr-defined]
    cassette_get_mod = ModuleType("sdetkit.core.cassette_get")
    cassette_get_mod.cassette_get = lambda argv: len(argv)  # type: ignore[attr-defined]
    atomicio_mod = ModuleType("sdetkit.core.atomicio")
    atomicio_mod.atomic_write_text = lambda *_a, **_k: None  # type: ignore[attr-defined]
    security_mod = ModuleType("sdetkit.core.security")
    security_mod.SecurityError = RuntimeError  # type: ignore[attr-defined]
    security_mod.safe_path = lambda p: p  # type: ignore[attr-defined]
    cli_mod = ModuleType("sdetkit.core.cli")
    cli_mod.main = lambda: 0  # type: ignore[attr-defined]

    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core", core_pkg)
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.cassette_get", cassette_get_mod)
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.atomicio", atomicio_mod)
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.security", security_mod)
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.cli", cli_mod)

    spec = importlib.util.spec_from_file_location("sdetkit.core.__main__", src_root / "__main__.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(__import__("sys").modules, "sdetkit.core.__main__", module)
    spec.loader.exec_module(module)
    return module, cli_mod


def test_core_main_edge_paths(monkeypatch, capsys) -> None:
    module, cli_mod = _load_core_main(monkeypatch)

    monkeypatch.setattr(module.sys, "argv", ["prog", "cassette-get", "x"])
    assert module.main() == 1

    cli_mod.main = lambda: (_ for _ in ()).throw(SystemExit(None))  # type: ignore[assignment]
    monkeypatch.setattr(module.sys, "argv", ["prog"])
    assert module.main() == 0

    cli_mod.main = lambda: (_ for _ in ()).throw(SystemExit(3))  # type: ignore[assignment]
    assert module.main() == 3

    cli_mod.main = lambda: (_ for _ in ()).throw(SystemExit("boom"))  # type: ignore[assignment]
    assert module.main() == 1
    assert "boom" in capsys.readouterr().err


def test_core_main_cassette_get_exception_path(monkeypatch, capsys) -> None:
    module, _ = _load_core_main(monkeypatch)
    monkeypatch.setattr(
        module, "_cassette_get", lambda _argv: (_ for _ in ()).throw(RuntimeError("kaboom"))
    )
    monkeypatch.setattr(module.sys, "argv", ["prog", "cassette-get", "x"])
    assert module.main() == 2
    assert "kaboom" in capsys.readouterr().err
