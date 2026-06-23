from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

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


def test_command_center_live_scan_lines_include_queue_snapshot_status() -> None:
    module = _load_module()

    live_scan = {
        "generated_at": "2026-06-09T00:00:00Z",
        "source": "GitHub API live scan",
        "open_pull_requests": {"available": True, "count": 0, "items": []},
        "open_issues_excluding_command_center": {"available": True, "count": 2, "items": []},
        "recent_workflow_runs": {
            "available": True,
            "total": 0,
            "counts": {"success": 0, "failure": 0, "pending": 0, "other": 0},
            "latest_failures": [],
        },
        "security_alerts": {
            "dependabot": {"available": True, "count": 0},
            "code_scanning": {"available": True, "count": 0},
            "secret_scanning": {"available": True, "count": 0},
        },
    }

    rendered = "\n".join(module._live_scan_lines(live_scan))

    assert "## Live repository scan" in rendered
    assert "Queue snapshot status: **fresh_no_open_prs**" in rendered
    assert "open PRs **0**, open issues **2**" in rendered
    assert "Next allowed action: `continue_roadmap_selection`" in rendered


def test_command_center_queue_snapshot_detects_stale_pr_samples() -> None:
    module = _load_module()

    live_scan = {
        "open_pull_requests": {
            "available": True,
            "count": 1,
            "items": [
                {
                    "number": 1657,
                    "title": "ci: add workflow permission review intelligence",
                    "state": "closed",
                }
            ],
        },
        "open_issues_excluding_command_center": {
            "available": True,
            "count": 6,
            "items": [],
        },
    }

    summary = module._queue_snapshot_summary(live_scan)

    assert summary["status"] == "stale"
    assert summary["stale_open_pr_sample_count"] == 1
    assert summary["next_allowed_action"] == "refresh_command_center_snapshot"

    rendered = "\n".join(module._queue_snapshot_lines(live_scan))
    assert "Queue snapshot status: **stale**" in rendered
    assert "Stale open PR samples detected: **1**" in rendered


def _payload_client(module, payload):
    class Client(module.GitHubClient):
        def _request(self, method, path, payload=None):
            return response

    response = payload
    return Client("example", "repo")


def test_valid_empty_collections_remain_authoritative_zero() -> None:
    module = _load_module()

    assert (
        _payload_client(module, []).paginate(
            "/repos/example/repo/pulls",
            {"state": "open"},
        )
        == []
    )
    assert (
        _payload_client(module, []).list_without_page(
            "/repos/example/repo/dependabot/alerts",
            {"state": "open"},
        )
        == []
    )
    assert (
        _payload_client(
            module,
            {"workflow_runs": []},
        ).list_recent_workflow_runs(limit=20)
        == []
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "unexpected success payload"},
        None,
    ],
)
def test_paginate_rejects_malformed_success_payloads(payload) -> None:
    module = _load_module()
    client = _payload_client(module, payload)

    with pytest.raises(
        RuntimeError,
        match=r"^GitHub API invalid payload GET .*expected list",
    ):
        client.paginate(
            "/repos/example/repo/pulls",
            {"state": "open"},
        )


def test_list_without_page_rejects_malformed_success_payload() -> None:
    module = _load_module()
    client = _payload_client(
        module,
        {"message": "unexpected success payload"},
    )

    with pytest.raises(
        RuntimeError,
        match=r"^GitHub API invalid payload GET .*expected list",
    ):
        client.list_without_page(
            "/repos/example/repo/dependabot/alerts",
            {"state": "open"},
        )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            ["unexpected", "list", "envelope"],
            "object",
        ),
        (
            {"workflow_runs": {"unexpected": "object"}},
            "workflow_runs list",
        ),
        (
            {},
            "workflow_runs list",
        ),
    ],
)
def test_workflow_scan_rejects_malformed_success_payloads(
    payload,
    expected,
) -> None:
    module = _load_module()
    client = _payload_client(module, payload)

    with pytest.raises(
        RuntimeError,
        match=rf"^GitHub API invalid payload GET .*expected {expected}",
    ):
        client.list_recent_workflow_runs(limit=20)


def test_queue_snapshot_honors_explicit_unavailability_without_error() -> None:
    module = _load_module()

    summary = module._queue_snapshot_summary(
        {
            "open_pull_requests": {
                "available": False,
                "count": None,
                "items": [],
                "error": "",
            },
            "open_issues_excluding_command_center": {
                "available": True,
                "count": 0,
                "items": [],
                "error": "",
            },
        }
    )

    assert summary == {
        "status": "unknown",
        "open_pr_count": None,
        "open_issue_count": 0,
        "stale_open_pr_sample_count": 0,
        "next_allowed_action": "retry_live_queue_scan",
    }


def test_collect_live_scan_marks_malformed_collections_unavailable() -> None:
    module = _load_module()
    client = _payload_client(
        module,
        {"message": "unexpected success payload"},
    )

    live_scan = module._collect_live_scan(
        client,
        open_issues=[],
        command_center_title="Maintenance command center",
        now_iso="2026-06-23T00:00:00Z",
    )

    assert live_scan["open_pull_requests"]["available"] is False
    assert live_scan["open_pull_requests"]["count"] is None
    assert live_scan["recent_workflow_runs"]["available"] is False
    assert live_scan["recent_workflow_runs"]["total"] is None
    assert live_scan["security_alerts"]["code_scanning"]["available"] is False
    assert live_scan["security_alerts"]["dependabot"]["available"] is False
    assert live_scan["security_alerts"]["secret_scanning"]["available"] is False

    rendered = "\n".join(module._live_scan_lines(live_scan))
    assert "Queue snapshot status: **unknown**" in rendered
    assert "Open pull requests: **unavailable**" in rendered
    assert "Recent workflow runs: **unavailable**" in rendered
    assert "GitHub API invalid payload" in rendered
