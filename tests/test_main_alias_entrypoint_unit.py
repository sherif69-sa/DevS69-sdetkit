from __future__ import annotations

import types

import pytest

import sdetkit.main_ as main_alias


def test_main_alias_routes_cassette_get_and_handles_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_alias.sys, "argv", ["sdetkit", "cassette-get", "demo"])
    monkeypatch.setattr(main_alias, "_cassette_get", lambda argv: 9)
    assert main_alias.main() == 9

    def _boom(_argv):
        raise RuntimeError("alias-boom")

    monkeypatch.setattr(main_alias, "_cassette_get", _boom)
    assert main_alias.main() == 2
    assert "alias-boom" in capsys.readouterr().err


def test_main_alias_cli_delegation_and_system_exit_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_alias.sys, "argv", ["sdetkit"])
    monkeypatch.setitem(
        main_alias.sys.modules,
        "sdetkit.__main__",
        types.SimpleNamespace(_run_cli_main=lambda: None),
    )
    assert main_alias.main() == 0

    def _raise_none():
        raise SystemExit(None)

    monkeypatch.setitem(
        main_alias.sys.modules,
        "sdetkit.__main__",
        types.SimpleNamespace(_run_cli_main=_raise_none),
    )
    assert main_alias.main() == 0

    def _raise_int():
        raise SystemExit(4)

    monkeypatch.setitem(
        main_alias.sys.modules,
        "sdetkit.__main__",
        types.SimpleNamespace(_run_cli_main=_raise_int),
    )
    assert main_alias.main() == 4

    def _raise_text():
        raise SystemExit("alias-exit")

    monkeypatch.setitem(
        main_alias.sys.modules,
        "sdetkit.__main__",
        types.SimpleNamespace(_run_cli_main=_raise_text),
    )
    assert main_alias.main() == 1
    assert "alias-exit" in capsys.readouterr().err


def test_main_alias_cassette_get_helper_wires_module_globals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sdetkit.cassette_get as mod

    marker_write = lambda *_a, **_k: None
    marker_safe = lambda p: p

    class MarkerError(Exception):
        pass

    monkeypatch.setattr(main_alias, "atomic_write_text", marker_write)
    monkeypatch.setattr(main_alias, "safe_path", marker_safe)
    monkeypatch.setattr(main_alias, "SecurityError", MarkerError)
    monkeypatch.setattr(main_alias, "_cassette_get_impl", lambda argv: 5)

    assert main_alias._cassette_get(["x"]) == 5
    assert mod.atomic_write_text is marker_write
    assert mod.safe_path is marker_safe
    assert mod.SecurityError is MarkerError
