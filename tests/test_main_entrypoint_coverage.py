from __future__ import annotations

import types

import pytest

import sdetkit.__main__ as entry


def test_main_routes_cassette_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit", "cassette-get", "demo"])
    monkeypatch.setattr(entry, "_cassette_get", lambda argv: 7)

    assert entry.main() == 7


def test_main_cassette_get_exception_writes_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit", "cassette-get"])

    def _boom(_: list[str]) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(entry, "_cassette_get", _boom)

    assert entry.main() == 2
    assert capsys.readouterr().err == "boom\n"


def test_main_cli_none_becomes_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit"])
    monkeypatch.setitem(entry.sys.modules, "sdetkit.cli", types.SimpleNamespace(main=lambda: None))

    assert entry.main() == 0


def test_main_system_exit_none_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit"])

    def _raise_none() -> int:
        raise SystemExit(None)

    monkeypatch.setitem(entry.sys.modules, "sdetkit.cli", types.SimpleNamespace(main=_raise_none))

    assert entry.main() == 0


def test_main_system_exit_int_returns_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit"])

    def _raise_int() -> int:
        raise SystemExit(3)

    monkeypatch.setitem(entry.sys.modules, "sdetkit.cli", types.SimpleNamespace(main=_raise_int))

    assert entry.main() == 3


def test_main_system_exit_text_returns_one_and_prints(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit"])

    def _raise_text() -> int:
        raise SystemExit("bye")

    monkeypatch.setitem(entry.sys.modules, "sdetkit.cli", types.SimpleNamespace(main=_raise_text))

    assert entry.main() == 1
    assert capsys.readouterr().err == "bye\n"


def test_cassette_get_helper_delegates_and_casts(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[list[str]] = []

    def _fake_cassette_get(argv: list[str]) -> str:
        called.append(argv)
        return "11"

    monkeypatch.setitem(entry.sys.modules, "sdetkit.cassette_get", types.SimpleNamespace(cassette_get=_fake_cassette_get))

    assert entry._cassette_get(["--flag", "value"]) == 11
    assert called == [["--flag", "value"]]


def test_run_cli_main_helper_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(entry.sys.modules, "sdetkit.cli", types.SimpleNamespace(main=lambda: 4))

    assert entry._run_cli_main() == 4


def test_main_cli_string_code_is_cast_to_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.sys, "argv", ["sdetkit"])
    monkeypatch.setattr(entry, "_run_cli_main", lambda: "9")

    assert entry.main() == 9
