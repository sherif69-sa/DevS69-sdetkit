from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from sdetkit import cli, serve


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310 - local server in test
        body = json.loads(resp.read().decode("utf-8"))
        return int(resp.status), body


def test_cli_dispatches_serve(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run(module_name: str, args: list[str]) -> int:
        called["module"] = module_name
        called["args"] = args
        return 0

    monkeypatch.setattr(cli, "_run_module_main", fake_run)
    rc = cli.main(["serve", "--host", "0.0.0.0", "--port", "9999"])

    assert rc == 0
    assert called["module"] == "sdetkit.serve"
    assert called["args"] == ["--host", "0.0.0.0", "--port", "9999"]


def test_serve_health_review_operator_mode_and_validation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[tool.sdetkit]\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    server = serve.build_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz") as resp:  # noqa: S310
            health = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert health["status"] == "ok"
        assert health["review_contract_version"] == "sdetkit.review.contract.v1"

        status, response = _post_json(
            f"http://127.0.0.1:{port}/v1/review",
            {
                "path": str(repo),
                "profile": "release",
                "response_mode": "operator-summary",
                "no_workspace": True,
                "out_dir": str(out_dir),
                "work_id": "TASK-99",
                "work_context": {"owner": "ops", "lane": "adaptive-review"},
            },
        )
        assert status == 200
        assert response["status"] == "ok"
        result = response["result"]
        assert "payload" not in result
        assert result["operator_summary"]["contract_version"] == "sdetkit.review.contract.v1"
        assert result["operator_summary"]["request_context"]["work_id"] == "TASK-99"
        assert result["operator_summary"]["request_context"]["work_context"]["lane"] == (
            "adaptive-review"
        )

        _, response2 = _post_json(
            f"http://127.0.0.1:{port}/v1/review",
            {
                "path": str(repo),
                "profile": "release",
                "response_mode": "operator-summary",
                "no_workspace": True,
                "out_dir": str(out_dir),
                "work_id": "TASK-99",
                "work_context": {"owner": "ops", "lane": "adaptive-review"},
            },
        )
        assert response2["result"]["operator_summary"] == result["operator_summary"]

        bad_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/review",
            data=json.dumps({"profile": "release"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(bad_req)  # noqa: S310
            raise AssertionError("expected validation error")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            err = json.loads(exc.read().decode("utf-8"))
            assert err["error"]["code"] == "validation_error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_serve_review_accepts_code_scan_json_and_returns_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[tool.sdetkit]\n", encoding="utf-8")
    scan = tmp_path / "scan.json"
    scan.write_text(
        json.dumps({"alerts": [{"severity": "critical", "rule_id": "sec-1"}]}),
        encoding="utf-8",
    )

    server = serve.build_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        status, response = _post_json(
            f"http://127.0.0.1:{port}/v1/review",
            {
                "path": str(repo),
                "profile": "release",
                "response_mode": "full",
                "no_workspace": True,
                "code_scan_json": str(scan),
            },
        )
        assert status == 200
        payload = response["result"]["payload"]
        assert payload["code_scanning"]["blocking_alerts"] == 1
        assert payload["artifact_index"]["code_scan_json"] == str(scan)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
