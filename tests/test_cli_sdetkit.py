import json

import httpx

from sdetkit import apiget, cli


class _DummyClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self._i = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None, timeout=None):
        if self._i >= len(self._responses):
            raise RuntimeError("no more responses")
        r = self._responses[self._i]
        self._i += 1
        return r


def test_sdetkit_apiget_dict_success(monkeypatch, capsys):
    req = httpx.Request("GET", "https://example.test/x")
    r = httpx.Response(200, json={"ok": True}, request=req)

    monkeypatch.setattr(apiget.httpx, "Client", lambda: _DummyClient([r]))
    rc = cli.main(["apiget", "https://example.test/x", "--expect", "dict"])
    assert rc == 0

    out = capsys.readouterr().out
    assert json.loads(out) == {"ok": True}


def test_sdetkit_apiget_list_paginate(monkeypatch, capsys):
    req1 = httpx.Request("GET", "https://example.test/p1")
    r1 = httpx.Response(
        200,
        json=[1],
        headers={"Link": '<https://example.test/p2>; rel="next"'},
        request=req1,
    )

    req2 = httpx.Request("GET", "https://example.test/p2")
    r2 = httpx.Response(200, json=[2], request=req2)

    monkeypatch.setattr(apiget.httpx, "Client", lambda: _DummyClient([r1, r2]))
    rc = cli.main(["apiget", "https://example.test/p1", "--expect", "list", "--paginate"])
    assert rc == 0

    out = capsys.readouterr().out
    assert json.loads(out) == [1, 2]


def test_sdetkit_apiget_expect_dict_mismatch_is_error(monkeypatch, capsys):
    req = httpx.Request("GET", "https://example.test/x")
    r = httpx.Response(200, json=[1], request=req)

    monkeypatch.setattr(apiget.httpx, "Client", lambda: _DummyClient([r]))
    rc = cli.main(["apiget", "https://example.test/x", "--expect", "dict"])
    assert rc == 1

    err = capsys.readouterr().err
    assert "expected json object" in err

def test_python_m_sdetkit_help():
    import subprocess
    import sys

    p = subprocess.run(
        [sys.executable, "-m", "sdetkit", "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert p.returncode == 0
    assert "usage: sdetkit" in p.stdout


def test_kvcli_help():
    import subprocess
    import sysconfig
    from pathlib import Path

    scripts = Path(sysconfig.get_path("scripts"))
    kv = scripts / "kvcli"
    if not kv.exists():
        kv = scripts / "kvcli.exe"

    p = subprocess.run(
        [str(kv) if kv.exists() else "kvcli", "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert p.returncode == 0
    assert "usage:" in p.stdout

def test_apigetcli_help():
    import subprocess
    import sysconfig
    from pathlib import Path

    scripts = Path(sysconfig.get_path("scripts"))
    apiget = scripts / "apigetcli"
    if not apiget.exists():
        apiget = scripts / "apigetcli.exe"

    p = subprocess.run(
        [str(apiget) if apiget.exists() else "apigetcli", "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert p.returncode == 0
    assert "usage:" in p.stdout
