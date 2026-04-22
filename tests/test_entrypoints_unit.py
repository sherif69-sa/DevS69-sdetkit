from __future__ import annotations

import pytest

import sdetkit.entrypoints as entrypoints


def test_kvcli_entrypoint_rewrites_argv_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoints.sys, "argv", ["kvcli", "--strict", "a=1"])
    monkeypatch.setattr(entrypoints, "main", lambda: 12)

    with pytest.raises(SystemExit) as excinfo:
        entrypoints.kvcli()

    assert excinfo.value.code == 12
    assert entrypoints.sys.argv == ["kvcli", "kv", "--strict", "a=1"]


def test_apigetcli_entrypoint_rewrites_argv_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoints.sys, "argv", ["apigetcli", "https://example.test"])
    monkeypatch.setattr(entrypoints, "main", lambda: 7)

    with pytest.raises(SystemExit) as excinfo:
        entrypoints.apigetcli()

    assert excinfo.value.code == 7
    assert entrypoints.sys.argv == ["apigetcli", "apiget", "https://example.test"]
