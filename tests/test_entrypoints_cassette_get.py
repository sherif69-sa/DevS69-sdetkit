from __future__ import annotations

import importlib
import json
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib
from pathlib import Path

import httpx

from sdetkit.cassette import Cassette, CassetteRecordTransport


def _entry_callable():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = (data.get("project") or {}).get("scripts") or {}
    cmd = "sdetkit" if "sdetkit" in scripts else next(iter(scripts))
    mod, fn = scripts[cmd].split(":", 1)
    return getattr(importlib.import_module(mod.strip()), fn.strip())


def _make_cassette(path: Path, url: str) -> None:
    cass = Cassette()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == url
        return httpx.Response(200, json={"ok": True})

    inner = httpx.MockTransport(handler)
    transport = CassetteRecordTransport(cass, inner)

    with httpx.Client(transport=transport) as client:
        r = client.get(url)
        r.raise_for_status()

    cass.save(path)


def test_entrypoints_cassette_get_replay_ok(tmp_path: Path, monkeypatch, capsys) -> None:
    url = "https://example.test/x"
    p = tmp_path / "cassette.json"
    _make_cassette(p, url)

    monkeypatch.setattr(sys, "argv", ["sdetkit", "cassette-get", "--replay", str(p), url])
    fn = _entry_callable()

    try:
        rc = fn()
    except SystemExit as e:
        rc = e.code

    if rc is None:
        rc = 0

    out = capsys.readouterr().out
    assert int(rc) == 0
    assert json.loads(out) == {"ok": True}
