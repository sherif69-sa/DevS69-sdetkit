from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "maintenance-autopilot.yml"
)


def test_workflow_runs_on_pull_request() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "on:" in text
    assert "pull_request:" in text


def test_pull_request_branch_avoids_live_remediation_flags() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'if [ "${{ github.event_name }}" = "pull_request" ]; then' in text
    assert "--run-live-if-token" in text
    assert "--auto-remediate-safe" in text
    pr_branch = text.split('if [ "${{ github.event_name }}" = "pull_request" ]; then', 1)[1].split(
        "else", 1
    )[0]
    assert "--run-live-if-token" not in pr_branch
    assert "--auto-remediate-safe" not in pr_branch


def test_side_effect_steps_are_guarded_for_non_pr_events() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Open/update security follow-up issue when actionable findings exist" in text
    assert "if: github.event_name != 'pull_request'" in text
    assert "Send webhook notification for actionable security follow-up" in text
    assert "Create pull request for successful auto-remediation" in text
