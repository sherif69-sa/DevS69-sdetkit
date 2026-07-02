from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-readiness-radar-bot.yml"


def test_healthy_release_readiness_run_is_artifact_only() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    healthy_guard = "if (!actionable) {"
    create_call = "await github.rest.issues.create({"

    assert "id: radar" in workflow
    assert "build/release-readiness-policy.json" in workflow
    assert "ACTIONABLE: ${{ steps.radar.outputs.actionable }}" in workflow
    assert "'zero_signal_issue_creation': False" in workflow
    assert healthy_guard in workflow
    assert "release readiness healthy; artifacts uploaded; no issue created" in workflow
    assert "return;" in workflow[workflow.index(healthy_guard) : workflow.rindex(create_call)]
    assert workflow.index(healthy_guard) < workflow.rindex(create_call)


def test_release_readiness_uses_one_bot_managed_rolling_tracker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "const rollingTitle = '🚀 Release readiness follow-up';" in workflow
    assert (
        "const generatedBodyMarker = '<!-- sdetkit:release-readiness-tracker:v1 -->';"
        in workflow
    )
    assert "issue.user?.login === 'github-actions[bot]'" in workflow
    assert "issue.title.startsWith('🚀 Release readiness radar')" in workflow
    assert "state_reason: 'completed'" in workflow
    assert "const weekOf" not in workflow


def test_release_readiness_requires_complete_evidence_before_suppressing_tracker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "doctor_evidence_available" in workflow
    assert "automation_evidence_available" in workflow
    assert "doctor evidence unavailable or malformed" in workflow
    assert "automation evidence unavailable or malformed" in workflow
    assert "missing_release_workflows" in workflow
    assert "missing_release_assets" in workflow
    assert "actionable = bool(actionable_reasons)" in workflow
    assert "'issue_policy': 'rolling_tracker_when_actionable'" in workflow


def test_generated_build_outputs_do_not_create_release_readiness_issue() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    policy_start = workflow.index("actionable_reasons = []")
    policy_end = workflow.index("actionable = bool(actionable_reasons)")
    policy_block = workflow[policy_start:policy_end]

    assert "dirty_files" not in policy_block
    assert "dirty_files" in workflow
