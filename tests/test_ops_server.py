from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from sdetkit.ops import create_server


def _wait_until_up(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5).read()
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.05)
    raise AssertionError(f"server did not start on port {port}: {last_error}")


@pytest.mark.network
def test_server_health_actions(tmp_path: Path) -> None:
    server = create_server("127.0.0.1", 0, tmp_path)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _wait_until_up(port)

    health = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
    payload = json.loads(health.decode("utf-8"))
    assert payload["ok"] is True

    actions = urllib.request.urlopen(f"http://127.0.0.1:{port}/actions", timeout=2).read()
    ap = json.loads(actions.decode("utf-8"))
    assert any(item["name"] == "repo.audit" for item in ap["actions"])

    server.shutdown()
    server.server_close()


@pytest.mark.network
def test_server_rejects_invalid_run_id(tmp_path: Path) -> None:
    server = create_server("127.0.0.1", 0, tmp_path)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _wait_until_up(port)

    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/runs/../etc/passwd", timeout=2)
    except Exception as exc:  # noqa: BLE001
        assert "HTTP Error 400" in str(exc)
    else:
        raise AssertionError("expected 400")

    server.shutdown()
    server.server_close()


@pytest.mark.network
def test_server_rejects_run_workflow_path_with_directories(tmp_path: Path) -> None:
    server = create_server("127.0.0.1", 0, tmp_path)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _wait_until_up(port)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/run-workflow",
        data=json.dumps({"workflow_path": "nested/wf.toml", "inputs": {}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(Exception) as exc:  # noqa: BLE001
        urllib.request.urlopen(req, timeout=2).read()
    assert "HTTP Error 400" in str(exc.value)

    server.shutdown()
    server.server_close()
