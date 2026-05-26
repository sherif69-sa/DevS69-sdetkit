from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "maintenance-autopilot.yml"
)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_runs_on_pull_request() -> None:
    text = _workflow_text()

    assert "on:" in text
    assert "pull_request:" in text


def test_workflow_preserves_reporting_permissions_without_repository_write() -> None:
    text = _workflow_text()
    permissions = text.split("jobs:", 1)[0]

    assert "contents: read" in permissions
    assert "contents: write" not in permissions
    assert "issues: write" in permissions
    assert "pull-requests: write" in permissions


def test_pull_request_branch_cannot_commit_unverified_remediation() -> None:
    text = _workflow_text()
    pr_branch = text.split(
        'if [ "${{ github.event_name }}" = "pull_request" ]; then',
        1,
    )[1].split("else", 1)[0]

    assert "--commit-safe-fixes" not in pr_branch
    assert "--run-live-if-token" not in pr_branch
    assert "--auto-remediate-safe" not in pr_branch


def test_non_pr_workflow_does_not_open_unverified_remediation_pull_request() -> None:
    text = _workflow_text()

    assert "--auto-remediate-safe" not in text
    assert "Detect successful auto-remediation changes" not in text
    assert "Create pull request for successful auto-remediation" not in text


def test_security_follow_up_side_effects_remain_non_pr_only() -> None:
    text = _workflow_text()

    assert "Open/update security follow-up issue when actionable findings exist" in text
    assert "if: github.event_name != 'pull_request'" in text
    assert "Send webhook notification for actionable security follow-up" in text
