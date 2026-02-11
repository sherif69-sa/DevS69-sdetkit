from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sdetkit import __main__ as mainmod


class _Resp:
    def __init__(self, payload: dict[str, object] | None = None, status_code: int = 200) -> None:
        self._payload = payload or {"ok": True}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def json(self) -> dict[str, object]:
        return self._payload


class _Client:
    def __init__(self, *args, **kwargs) -> None:
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, _url: str) -> _Resp:
        return _Resp({"ok": True})


def test_cassette_get_record_refuses_overwrite_without_force(tmp_path: Path, capsys) -> None:
    existing = tmp_path / "cassette.json"
    existing.write_text("{}", encoding="utf-8")

    old_cwd = Path.cwd()
    try:
        # safe_path resolves against cwd, so run from tmp_path
        import os

        os.chdir(tmp_path)
        rc = mainmod._cassette_get(["https://example.invalid", "--record", "cassette.json"])
    finally:
        os.chdir(old_cwd)

    err = capsys.readouterr().err
    assert rc == 2
    assert "refusing to overwrite existing cassette" in err


def test_cassette_get_replay_load_error_returns_2(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import sdetkit.cassette as cassette_mod

    monkeypatch.setattr(
        cassette_mod.Cassette, "load", lambda _p: (_ for _ in ()).throw(ValueError("boom"))
    )
    rc = mainmod._cassette_get(["https://example.invalid", "--replay", "x.json"])

    err = capsys.readouterr().err
    assert rc == 2
    assert "boom" in err


def test_cassette_get_plain_mode_writes_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import httpx

    monkeypatch.setattr(httpx, "Client", _Client)

    rc = mainmod._cassette_get(["https://example.invalid", "--insecure", "--follow-redirects"])
    out = capsys.readouterr()

    assert rc == 0
    assert json.loads(out.out) == {"ok": True}
    assert "TLS verification disabled" in out.err


def test_main_cassette_get_exception_path(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(
        mainmod, "_cassette_get", lambda _argv: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    old_argv = sys.argv[:]
    try:
        sys.argv = ["sdetkit", "cassette-get", "https://example.invalid"]
        rc = mainmod.main()
    finally:
        sys.argv = old_argv

    err = capsys.readouterr().err
    assert rc == 2
    assert "boom" in err
