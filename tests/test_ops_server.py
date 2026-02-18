from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from sdetkit.ops import serve


@pytest.mark.network
def test_server_health_actions(tmp_path: Path) -> None:
    port = 8877
    thread = threading.Thread(target=serve, args=("127.0.0.1", port, tmp_path), daemon=True)
    thread.start()
    time.sleep(0.1)

    health = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read()
    payload = json.loads(health.decode("utf-8"))
    assert payload["ok"] is True

    actions = urllib.request.urlopen(f"http://127.0.0.1:{port}/actions", timeout=2).read()
    ap = json.loads(actions.decode("utf-8"))
    assert any(item["name"] == "repo.audit" for item in ap["actions"])


@pytest.mark.network
def test_server_rejects_invalid_run_id(tmp_path: Path) -> None:
    port = 8878
    thread = threading.Thread(target=serve, args=("127.0.0.1", port, tmp_path), daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/runs/../etc/passwd", timeout=2)
    except Exception as exc:  # noqa: BLE001
        assert "HTTP Error 400" in str(exc)
    else:
        raise AssertionError("expected 400")


@pytest.mark.network
def test_server_rejects_run_workflow_path_with_directories(tmp_path: Path) -> None:
    port = 8879
    thread = threading.Thread(target=serve, args=("127.0.0.1", port, tmp_path), daemon=True)
    thread.start()
    time.sleep(0.1)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/run-workflow",
        data=json.dumps({"workflow_path": "nested/wf.toml", "inputs": {}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(Exception) as exc:  # noqa: BLE001
        urllib.request.urlopen(req, timeout=2).read()
    assert "HTTP Error 400" in str(exc.value)
