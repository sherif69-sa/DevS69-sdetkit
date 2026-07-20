from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/legacy-required-status-bridge.yml")
PUBLISHER_JOBS = (
    "publish-legacy-statuses-on-pr-open",
    "publish-legacy-statuses-from-ci-workflow",
)


def _workflow() -> dict:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_legacy_status_publishers_retry_transient_github_api_failures() -> None:
    payload = _workflow()
    jobs = payload["jobs"]

    assert payload["permissions"]["statuses"] == "write"
    for job_name in PUBLISHER_JOBS:
        step = jobs[job_name]["steps"][0]
        assert step["with"]["retries"] == 4
        assert "github.rest.repos.createCommitStatus" in step["with"]["script"]


def test_legacy_status_contexts_and_authority_remain_unchanged() -> None:
    payload = _workflow()
    pull_request_script = payload["jobs"][PUBLISHER_JOBS[0]]["steps"][0]["with"]["script"]
    workflow_run_script = payload["jobs"][PUBLISHER_JOBS[1]]["steps"][0]["with"]["script"]

    assert "context: 'ci'" in pull_request_script
    assert "context: 'maintenance-autopilot'" in pull_request_script
    assert "state: 'pending'" in pull_request_script
    assert "state: 'success'" in pull_request_script
    assert "context: 'ci'" in workflow_run_script
    assert "conclusion === 'success' ? 'success' : 'failure'" in workflow_run_script
