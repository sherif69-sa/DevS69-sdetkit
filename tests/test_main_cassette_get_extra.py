from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sdetkit import main_ as mainmod


class _Resp:
    def init_(self, payload: dict[str, object] | None = None, status_code: int = 200) -> None:
        self._payload = payload or {"ok": True}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def json(self) -> dict[str, object]:
        return self._payload


class _Client:
    def init_(self, *args, **kwargs) -> None:
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, _url: str) -> _Resp:
        return _Resp({"ok": True})


class _ClientCaptureKwargs(_Client):
    last_kwargs: dict[str, object] | None = None

    def init_(self, *args, **kwargs) -> None:
        type(self).last_kwargs = dict(kwargs)
        super().init_(*args, **kwargs)


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


def test_main_delegates_to_cli_main_when_not_cassette_get(monkeypatch: pytest.MonkeyPatch) -> None:
    import sdetkit.cli as cli_mod

    monkeypatch.setattr(cli_mod, "main", lambda: None)

    old_argv = sys.argv[:]
    try:
        sys.argv = ["sdetkit", "doctor", "--help"]
        rc = mainmod.main()
    finally:
        sys.argv = old_argv

    assert rc == 0


def test_cassette_get_disallows_unapproved_scheme(capsys) -> None:
    rc = mainmod._cassette_get(["file:///tmp/nope.json"])
    io = capsys.readouterr()

    assert rc == 2
    assert "is not allowed" in io.err


def test_cassette_get_replay_allow_absolute_uses_assert_exhausted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    import httpx

    import sdetkit.cassette as cassette_mod

    seen: dict[str, object] = {}

    class _ReplayTransport:
        def init_(self, cass) -> None:
            seen["cass"] = cass

        def assert_exhausted(self) -> None:
            seen["assert_exhausted_called"] = True

    class _Client2(_Client):
        pass

    def fake_load(path: Path, allow_absolute: bool = False):
        seen["path"] = path
        seen["allow_absolute"] = allow_absolute
        return object()

    monkeypatch.setattr(cassette_mod.Cassette, "load", staticmethod(fake_load))
    monkeypatch.setattr(cassette_mod, "CassetteReplayTransport", _ReplayTransport)
    monkeypatch.setattr(httpx, "Client", _Client2)

    p = tmp_path / "replay.json"
    p.write_text("{}", encoding="utf-8")

    rc = mainmod._cassette_get(
        ["https://example.invalid", "--replay", str(p), "--allow-absolute-path"]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True}
    assert seen["path"] == p
    assert seen["allow_absolute"] is True
    assert seen["assert_exhausted_called"] is True


def test_cassette_get_record_force_writes_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import httpx

    import sdetkit.cassette as cassette_mod

    seen: dict[str, object] = {}

    class _FakeCassette:
        def to_json(self):
            return {"records": [{"method": "GET", "url": "https://example.invalid"}]}

    class _RecordTransport:
        def init_(self, cass, inner) -> None:
            seen["cass"] = cass
            seen["inner"] = inner

    monkeypatch.setattr(cassette_mod, "Cassette", _FakeCassette)
    monkeypatch.setattr(cassette_mod, "CassetteRecordTransport", _RecordTransport)
    monkeypatch.setattr(httpx, "Client", _Client)
    monkeypatch.setattr(httpx, "HTTPTransport", lambda: "http-transport")
    monkeypatch.setattr(
        mainmod,
        "atomic_write_text",
        lambda path, payload: seen.update({"path": path, "payload": payload}),
    )

    out_path = tmp_path / "cassette.json"
    out_path.write_text("{}", encoding="utf-8")

    old_cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        rc = mainmod._cassette_get(
            ["https://example.invalid", "--record", "cassette.json", "--force"]
        )
    finally:
        os.chdir(old_cwd)

    assert rc == 0
    assert seen["path"] == out_path
    assert '"records"' in str(seen["payload"])


def test_cassette_get_allow_scheme_accepts_extra_scheme(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import httpx

    monkeypatch.setattr(httpx, "Client", _Client)

    rc = mainmod._cassette_get(["ftp://example.invalid", "--allow-scheme", "ftp"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True}


def test_cassette_get_record_safe_path_security_error(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(
        mainmod,
        "safe_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(mainmod.SecurityError("blocked path")),
    )

    rc = mainmod._cassette_get(["https://example.invalid", "--record", "../escape.json"])
    io = capsys.readouterr()
    assert rc == 2
    assert "blocked path" in io.err


def test_cassette_get_plain_mode_passes_explicit_httpx_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    monkeypatch.setattr(httpx, "Client", _ClientCaptureKwargs)
    _ClientCaptureKwargs.last_kwargs = None

    rc = mainmod._cassette_get(["https://example.invalid", "--insecure", "--follow-redirects"])

    assert rc == 0
    assert _ClientCaptureKwargs.last_kwargs is not None
    assert _ClientCaptureKwargs.last_kwargs["verify"] is False
    assert _ClientCaptureKwargs.last_kwargs["follow_redirects"] is True
    assert "timeout" in _ClientCaptureKwargs.last_kwargs


def test_cassette_get_replay_mode_passes_transport_and_explicit_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import httpx

    import sdetkit.cassette as cassette_mod

    class _ReplayTransport:
        def init_(self, _cass) -> None:
            pass

        def assert_exhausted(self) -> None:
            return None

    monkeypatch.setattr(httpx, "Client", _ClientCaptureKwargs)
    monkeypatch.setattr(cassette_mod.Cassette, "load", staticmethod(lambda *_a, **_k: object()))
    monkeypatch.setattr(cassette_mod, "CassetteReplayTransport", _ReplayTransport)
    _ClientCaptureKwargs.last_kwargs = None

    p = tmp_path / "replay.json"
    p.write_text("{}", encoding="utf-8")

    rc = mainmod._cassette_get(
        [
            "https://example.invalid",
            "--replay",
            str(p),
            "--allow-absolute-path",
            "--follow-redirects",
        ]
    )

    assert rc == 0
    assert _ClientCaptureKwargs.last_kwargs is not None
    assert _ClientCaptureKwargs.last_kwargs["follow_redirects"] is True
    assert _ClientCaptureKwargs.last_kwargs["verify"] is True
    assert "transport" in _ClientCaptureKwargs.last_kwargs
