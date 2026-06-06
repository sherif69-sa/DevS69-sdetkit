from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "maintenance_command_center.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("maintenance_command_center", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_command_center_body_includes_live_repository_scan() -> None:
    module = _load_module()

    live_scan = {
        "generated_at": "2026-06-05T19:30:00Z",
        "source": "GitHub API live scan at command runtime",
        "open_pull_requests": {"available": True, "count": 0, "items": [], "error": ""},
        "open_issues_excluding_command_center": {
            "available": True,
            "count": 0,
            "items": [],
            "error": "",
        },
        "recent_workflow_runs": {
            "available": True,
            "total": 2,
            "counts": {"success": 1, "failure": 0, "pending": 1, "other": 0},
            "latest_failures": [],
            "error": "",
        },
        "security_alerts": {
            "code_scanning": {"available": True, "count": 0, "error": ""},
            "dependabot": {
                "available": False,
                "count": None,
                "error": "Resource not accessible by integration",
            },
            "secret_scanning": {"available": True, "count": 0, "error": ""},
        },
    }

    body = module._build_body(
        now_iso="2026-06-05T19:30:00Z",
        keep_open=[],
        deferred=[],
        command_center_title="🧠 Maintenance command center (rolling)",
        review_payload={},
        doctor_payload={"score": 100},
        rollup_payload={},
        live_scan=live_scan,
        max_open_trackers=4,
    )

    assert "## Live repository scan" in body
    assert "Source: **GitHub API live scan at command runtime**" in body
    assert "Open pull requests: **0**" in body
    assert "Open issues excluding command center: **0**" in body
    assert (
        "Recent workflow runs: **2** scanned; success **1**, failure **0**, pending **1**" in body
    )
    assert "Code scanning open alerts: **0**" in body
    assert "Dependabot open alerts: **unavailable**" in body
    assert "Secret scanning open alerts: **0**" in body


def test_alert_scan_falls_back_when_endpoint_rejects_page_parameter() -> None:
    module = _load_module()

    class Client:
        requested_path = ""
        requested_params = {}

        def paginate(self, path, params=None):
            raise RuntimeError(
                "GitHub API error 400 GET /dependabot/alerts: "
                '{"message":"Pagination using the `page` parameter is not supported."}'
            )

        def list_without_page(self, path, params=None):
            self.requested_path = path
            self.requested_params = dict(params or {})
            return [{"number": 1}, {"number": 2}]

    client = Client()
    scan = module._alert_scan(client, "/repos/example/repo/dependabot/alerts")

    assert scan == {"available": True, "count": 2, "error": ""}
    assert client.requested_path == "/repos/example/repo/dependabot/alerts"
    assert client.requested_params == {"state": "open"}
