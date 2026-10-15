from __future__ import annotations

import importlib
import importlib.util
import json
import runpy
from pathlib import Path
from types import ModuleType

import pytest


def test_entrypoint_shims_cast_return_values(monkeypatch) -> None:
    mod = importlib.import_module("sdetkit._entrypoints")
    monkeypatch.setattr(mod, "_kvcli_main", lambda: True)
    monkeypatch.setattr(mod, "_apiget_main", lambda: False)

    assert mod.kvcli() == 1
    assert mod.apigetcli() == 0


def test_core_toml_loader_prefers_tomllib(monkeypatch) -> None:
    mod = importlib.import_module("sdetkit._toml")
    monkeypatch.setattr(mod.sys, "version_info", (3, 11, 0))
    calls: list[str] = []

    def _fake_import(name: str):
        calls.append(name)

        class _Fake:
            @staticmethod
            def loads(text: str):
                return {"raw": text}

        return _Fake()

    monkeypatch.setattr(mod, "import_module", _fake_import)

    loaded = mod._load_toml_module()
    assert loaded.loads("a=1") == {"raw": "a=1"}
    assert calls == ["tomllib"]


def test_core_toml_loader_uses_tomli_on_older_python(monkeypatch) -> None:
    mod = importlib.import_module("sdetkit._toml")
    monkeypatch.setattr(mod.sys, "version_info", (3, 10, 9))
    calls: list[str] = []

    monkeypatch.setattr(mod, "import_module", lambda name: calls.append(name) or object())
    mod._load_toml_module()

    assert calls == ["tomli"]


def test_contract_runtime_json_and_text(tmp_path: Path, capsys, monkeypatch) -> None:
    root = tmp_path
    surface = root / "src" / "sdetkit"
    surface.mkdir(parents=True)
    (surface / "public_command_surface.json").write_text(
        json.dumps(
            {
                "contract_version": "v99",
                "canonical_first_path": ["python -m sdetkit gate fast"],
                "public_stable_front_door_commands": ["sdetkit gate fast"],
                "advanced_supported_next_step": "python -m sdetkit doctor",
            }
        ),
        encoding="utf-8",
    )

    mod = importlib.import_module("sdetkit.contract")
    monkeypatch.setattr(mod, "_tool_version", lambda: "1.2.3")

    assert mod.main(["runtime", "--format", "json", "--repo-root", str(root)]) == 0
    out_json = capsys.readouterr().out
    payload = json.loads(out_json)
    assert payload["tool"]["version"] == "1.2.3"
    assert payload["stability_surfaces"]["public_command_surface_version"] == "v99"

    assert mod.main(["runtime", "--format", "text", "--repo-root", str(root)]) == 0
    out_text = capsys.readouterr().out
    assert "runtime_contract_version:" in out_text
    assert "tool: sdetkit@1.2.3" in out_text


def test_checks_and_maintenance_main_modules(monkeypatch) -> None:
    checks_main = importlib.import_module("sdetkit.checks.main")
    monkeypatch.setattr(checks_main, "main", lambda: 12)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sdetkit.checks.__main__", run_name="__main__")
    assert exc.value.code == 12

    maintenance_main = importlib.import_module("sdetkit.maintenance.main")
    monkeypatch.setattr(maintenance_main, "main", lambda: 34)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sdetkit.maintenance.__main__", run_name="__main__")
    assert exc.value.code == 34


def test_compat_reexport_modules_surface_names() -> None:
    serve = importlib.import_module("sdetkit.serve")
    security = importlib.import_module("sdetkit.cli.security")

    assert "main" in serve.__all__
    assert "safe_path" in security.__all__


def test_core_main_module_paths_with_stubbed_package(monkeypatch, capsys) -> None:
    src_root = Path(__file__).resolve().parents[1] / "src"
    core_path = src_root / "sdetkit" / "core"

    core_pkg = ModuleType("sdetkit.core")
    core_pkg.__path__ = [str(core_path)]  # type: ignore[attr-defined]

    cassette_get_mod = ModuleType("sdetkit.cassette_get")
    cassette_get_mod.cassette_get = lambda argv: len(argv)  # type: ignore[attr-defined]
    atomic_mod = ModuleType("sdetkit.atomicio")
    atomic_mod.atomic_write_text = lambda *_a, **_k: None  # type: ignore[attr-defined]
    security_mod = ModuleType("sdetkit.security")
    security_mod.SecurityError = RuntimeError  # type: ignore[attr-defined]
    security_mod.safe_path = lambda p: p  # type: ignore[attr-defined]
    cli_mod = ModuleType("sdetkit.cli")
    cli_mod.main = lambda: 0  # type: ignore[attr-defined]

    monkeypatch.setitem(importlib.sys.modules, "sdetkit.core", core_pkg)
    monkeypatch.setitem(importlib.sys.modules, "sdetkit.cassette_get", cassette_get_mod)
    monkeypatch.setitem(importlib.sys.modules, "sdetkit.atomicio", atomic_mod)
    monkeypatch.setitem(importlib.sys.modules, "sdetkit.security", security_mod)
    monkeypatch.setitem(importlib.sys.modules, "sdetkit.cli", cli_mod)

    spec = importlib.util.spec_from_file_location(
        "sdetkit.core.__main__", core_path / "__main__.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(importlib.sys.modules, "sdetkit.core.__main__", mod)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod.sys, "argv", ["prog", "cassette-get", "a", "b"])
    assert mod.main() == 2

    cli_mod.main = lambda: (_ for _ in ()).throw(SystemExit("boom"))  # type: ignore[assignment]
    monkeypatch.setattr(mod.sys, "argv", ["prog"])
    assert mod.main() == 1
    assert "boom" in capsys.readouterr().err
