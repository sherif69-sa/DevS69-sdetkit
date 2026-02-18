from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx

from sdetkit.cassette import Cassette, CassetteRecordTransport


def _make_cassette(path: Path, url: str) -> None:
    cass = Cassette()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == url
        return httpx.Response(200, json={"ok": True, "n": 1})

    inner = httpx.MockTransport(handler)
    transport = CassetteRecordTransport(cass, inner)

    with httpx.Client(transport=transport) as client:
        r = client.get(url)
        r.raise_for_status()

    cass.save(path, allow_absolute=True)


def test_cli_cassette_get_replay_ok(tmp_path: Path) -> None:
    url = "https://example.test/hello"
    p = tmp_path / "cassette.json"
    _make_cassette(p, url)

    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "cassette-get",
            "--replay",
            str(p),
            "--allow-absolute-path",
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"ok": True, "n": 1}


def test_cli_cassette_get_replay_mismatch(tmp_path: Path) -> None:
    url = "https://example.test/hello"
    p = tmp_path / "cassette.json"
    _make_cassette(p, url)

    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "cassette-get",
            "--replay",
            str(p),
            "--allow-absolute-path",
            "https://example.test/other",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert r.returncode != 0
    assert (r.stderr + r.stdout).strip()
