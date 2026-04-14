from __future__ import annotations

import sys
import types

from sdetkit.core_preparse_dispatch import dispatch_core_preparse


def test_dispatch_core_preparse_routes_doctor(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sdetkit.doctor", types.SimpleNamespace(main=lambda args: 41))
    assert dispatch_core_preparse(["doctor", "--format", "json"]) == 41


def test_dispatch_core_preparse_routes_gate(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sdetkit.gate", types.SimpleNamespace(main=lambda args: 7))
    assert dispatch_core_preparse(["gate", "fast"]) == 7


def test_dispatch_core_preparse_routes_ci(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sdetkit.ci", types.SimpleNamespace(main=lambda args: 3))
    assert dispatch_core_preparse(["ci", "validate"]) == 3


def test_dispatch_core_preparse_handles_cassette_get_exceptions(monkeypatch, capsys) -> None:
    def _boom(_args):
        raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "sdetkit.__main__", types.SimpleNamespace(_cassette_get=_boom))
    assert dispatch_core_preparse(["cassette-get", "foo"]) == 2
    captured = capsys.readouterr()
    assert "boom" in captured.err


def test_dispatch_core_preparse_returns_none_for_non_core_command() -> None:
    assert dispatch_core_preparse(["review", "repo"]) is None
