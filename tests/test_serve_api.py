from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sdetkit import cli, serve


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - local server in test
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
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as resp:  # noqa: S310
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
        result = cast(dict[str, Any], response["result"])
        assert "payload" not in result
        operator_summary = cast(dict[str, Any], result["operator_summary"])
        request_context = cast(dict[str, Any], operator_summary["request_context"])
        work_context = cast(dict[str, Any], request_context["work_context"])
        assert operator_summary["contract_version"] == "sdetkit.review.contract.v1"
        assert request_context["work_id"] == "TASK-99"
        assert work_context["lane"] == ("adaptive-review")

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
        result2 = cast(dict[str, Any], response2["result"])
        assert result2["operator_summary"] == result["operator_summary"]

        bad_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/review",
            data=json.dumps({"profile": "release"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(bad_req, timeout=5)  # noqa: S310
            raise AssertionError("expected validation error")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            err = json.loads(exc.read().decode("utf-8"))
            assert err["error"]["code"] == "validation_error"

        bad_scan_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/review",
            data=json.dumps({"path": str(repo), "code_scan_json": "nested/scan.json"}).encode(
                "utf-8"
            ),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(bad_scan_req, timeout=5)  # noqa: S310
            raise AssertionError("expected code_scan_json validation error")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_serve_review_accepts_code_scan_json_and_returns_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[tool.sdetkit]\n", encoding="utf-8")
    scan = repo / "scan.json"
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
                "code_scan_json": "scan.json",
            },
        )
        assert status == 200
        result = cast(dict[str, Any], response["result"])
        payload = cast(dict[str, Any], result["payload"])
        code_scanning = cast(dict[str, Any], payload["code_scanning"])
        artifact_index = cast(dict[str, Any], payload["artifact_index"])
        assert code_scanning["blocking_alerts"] == 1
        assert artifact_index["code_scan_json"] == str(scan)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_serve_observability_endpoint_reports_artifact_snapshot(tmp_path: Path) -> None:
    out = tmp_path / ".sdetkit" / "out"
    out.mkdir(parents=True)
    (out / "adoption-scorecard.json").write_text(
        json.dumps({"score": 75, "band": "strong", "overall_ok": True}),
        encoding="utf-8",
    )
    (out / "golden-path-health.json").write_text(
        json.dumps({"overall_ok": True}),
        encoding="utf-8",
    )

    cwd = Path.cwd()
    os.chdir(tmp_path)
    server = serve.build_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        status_url = f"http://127.0.0.1:{port}/v1/observability"
        with urllib.request.urlopen(status_url, timeout=5) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert payload["status"] == "ok"
        assert payload["observability_contract_version"] == "2"
        assert payload["captured_at"].endswith("Z")
        assert "freshness_summary" in payload
        assert "adoption_scorecard" in payload["observability"]
        adoption = payload["observability"]["adoption_scorecard"]
        assert adoption["artifact_mtime"].endswith("Z")
        assert isinstance(adoption["freshness_age_seconds"], int)
        assert adoption["stale"] in {True, False}
        assert adoption["stale_threshold_seconds"] == 86400
        missing = payload["observability"]["operator_onboarding_summary"]
        assert missing["state"] == "missing"
        assert missing["freshness_age_seconds"] is None
        assert missing["stale"] is True
        assert payload["freshness_summary"]["present"] >= 2
        assert payload["freshness_summary"]["missing"] >= 1
    finally:
        os.chdir(cwd)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_serve_observability_marks_stale_artifacts(tmp_path: Path) -> None:
    out = tmp_path / ".sdetkit" / "out"
    out.mkdir(parents=True)
    path = out / "golden-path-health.json"
    path.write_text(json.dumps({"overall_ok": True}), encoding="utf-8")
    stale_epoch = (datetime.now(tz=UTC) - timedelta(days=2)).timestamp()
    os.utime(path, (stale_epoch, stale_epoch))

    cwd = Path.cwd()
    os.chdir(tmp_path)
    server = serve.build_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/observability", timeout=5) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        golden = payload["observability"]["golden_path_health"]
        assert golden["state"] == "present"
        assert golden["freshness_age_seconds"] >= 172800
        assert golden["stale"] is True
    finally:
        os.chdir(cwd)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_serve_observability_allows_stale_threshold_overrides(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / ".sdetkit" / "out"
    out.mkdir(parents=True)
    path = out / "adoption-scorecard.json"
    path.write_text(json.dumps({"score": 90, "band": "excellent"}), encoding="utf-8")
    stale_epoch = (datetime.now(tz=UTC) - timedelta(seconds=120)).timestamp()
    os.utime(path, (stale_epoch, stale_epoch))

    monkeypatch.setenv("SDETKIT_OBSERVABILITY_STALE_SECONDS", "60")
    payload = serve._observability_snapshot(tmp_path)
    adoption = payload["observability"]["adoption_scorecard"]
    assert adoption["stale_threshold_seconds"] == 60
    assert adoption["stale"] is True

    monkeypatch.setenv("SDETKIT_OBSERVABILITY_STALE_ADOPTION_SCORECARD_SECONDS", "300")
    payload2 = serve._observability_snapshot(tmp_path)
    adoption2 = payload2["observability"]["adoption_scorecard"]
    assert adoption2["stale_threshold_seconds"] == 300
    assert adoption2["stale"] is False


def test_serve_observability_ignores_invalid_threshold_env(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / ".sdetkit" / "out"
    out.mkdir(parents=True)
    path = out / "adoption-scorecard.json"
    path.write_text(json.dumps({"score": 90}), encoding="utf-8")

    monkeypatch.setenv("SDETKIT_OBSERVABILITY_STALE_SECONDS", "invalid")
    payload = serve._observability_snapshot(tmp_path)
    adoption = payload["observability"]["adoption_scorecard"]
    assert adoption["stale_threshold_seconds"] == 86400
