from __future__ import annotations

import pytest

import sdetkit._entrypoints as private_entrypoints


def test_private_kvcli_casts_result_to_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(private_entrypoints, "_kvcli_main", lambda: "5")

    assert private_entrypoints.kvcli() == 5


def test_private_apigetcli_casts_result_to_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(private_entrypoints, "_apiget_main", lambda: "9")

    assert private_entrypoints.apigetcli() == 9
