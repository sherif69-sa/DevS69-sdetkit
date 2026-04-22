from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from sdetkit import premium_gate_engine as eng


def _get_json(url: str) -> tuple[int, dict[str, object]]:
    with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 local test server
        return int(resp.status), json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310 local test server
        return int(resp.status), json.loads(resp.read().decode("utf-8"))


def _put_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310 local test server
        return int(resp.status), json.loads(resp.read().decode("utf-8"))


def test_insights_handler_endpoints_cover_get_post_put(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    db_path = tmp_path / "insights.db"
    eng._init_db(db_path)

    eng._InsightsHandler.db_path = db_path
    eng._InsightsHandler.out_dir = out_dir

    server = eng.http.server.ThreadingHTTPServer(("127.0.0.1", 0), eng._InsightsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])

    try:
        status, health = _get_json(f"http://127.0.0.1:{port}/health")
        assert status == 200
        assert health["ok"] is True

        status2, create = _post_json(
            f"http://127.0.0.1:{port}/guidelines",
            {"title": "g1", "body": "do thing", "tags": ["a", "b"]},
        )
        assert status2 == 201
        gid = int(create["id"])

        status3, listing = _get_json(f"http://127.0.0.1:{port}/guidelines?active=1&limit=10")
        assert status3 == 200
        assert any(int(item["id"]) == gid for item in listing["guidelines"])

        status4, updated = _put_json(
            f"http://127.0.0.1:{port}/guidelines/{gid}",
            {"title": "g1-updated", "body": "new", "tags": ["x"], "active": False},
        )
        assert status4 == 200
        assert updated["ok"] is True

        status5, learn = _post_json(
            f"http://127.0.0.1:{port}/learn-commit",
            {"commit_sha": "abc123", "message": "msg", "changed_files": ["a.py"], "summary": "s"},
        )
        assert status5 == 201
        assert int(learn["id"]) >= 1

        status6, analyzed = _get_json(f"http://127.0.0.1:{port}/analyze")
        assert status6 == 200
        assert int(analyzed["run_id"]) >= 1
        assert isinstance(analyzed["payload"], dict)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_insights_handler_404_and_empty_payload_paths(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    db_path = tmp_path / "insights.db"
    eng._init_db(db_path)

    eng._InsightsHandler.db_path = db_path
    eng._InsightsHandler.out_dir = out_dir

    server = eng.http.server.ThreadingHTTPServer(("127.0.0.1", 0), eng._InsightsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])

    try:
        empty_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/guidelines", data=b"", method="POST", headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(empty_req, timeout=3) as resp:  # noqa: S310 local server
            created = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 201
            assert int(created["id"]) >= 1

        for method, path in (("GET", "/unknown"), ("POST", "/unknown"), ("PUT", "/guidelines/not-an-id")):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                data=b"{}" if method in {"POST", "PUT"} else None,
                method=method,
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                urllib.request.urlopen(req, timeout=3)
            assert excinfo.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
