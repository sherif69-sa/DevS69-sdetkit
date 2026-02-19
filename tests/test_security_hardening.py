from __future__ import annotations

import httpx

from sdetkit import apiget
from sdetkit.atomicio import atomic_write_text
from sdetkit.security import SecurityError, safe_path


class _FakeClient:
    def __init__(self, **_kwargs):
        self.headers = {"user-agent": "tests"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, timeout=None, **kwargs):
        req = httpx.Request(method, url, headers=kwargs.get("headers"))
        body = {"ok": True, "access_token": "super-secret"}
        return httpx.Response(200, request=req, json=body, headers={"set-cookie": "abc"})


def test_apiget_verbose_redacts_default(monkeypatch, capsys):
    monkeypatch.setattr(apiget.httpx, "Client", _FakeClient)
    rc = apiget.main(
        [
            "https://example.test/api?token=abc",
            "--method",
            "POST",
            "--json",
            '{"password":"p4ss"}',
            "--verbose",
            "--print-status",
            "--header",
            "Authorization: Bearer topsecret",
        ]
    )
    assert rc == 0
    err = capsys.readouterr().err.lower()
    assert "topsecret" not in err
    assert "token=abc" not in err
    assert "set-cookie: abc" not in err


def test_apiget_rejects_disallowed_scheme():
    try:
        apiget.main(["ftp://example.test/data"])
    except SystemExit as exc:
        assert int(exc.code) == 2
    else:
        raise AssertionError("expected SystemExit(2)")


def test_safe_path_blocks_traversal(tmp_path):
    try:
        safe_path(tmp_path, "../oops.txt")
    except SecurityError:
        pass
    else:
        raise AssertionError("expected traversal to be rejected")


def test_atomic_write_text_never_partial(tmp_path):
    target = tmp_path / "artifact.json"
    target.write_text("old", encoding="utf-8")

    def boom(_tmp, _dest):
        raise RuntimeError("boom")

    try:
        atomic_write_text(target, "new data", before_replace=boom)
    except RuntimeError:
        pass

    assert target.read_text(encoding="utf-8") == "old"


def test_safe_path_rejects_windows_absolute_without_allow(tmp_path):
    try:
        safe_path(tmp_path, "C:/windows/system32")
    except SecurityError:
        pass
    else:
        raise AssertionError("expected absolute windows path to be rejected")
