from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "adapter-smoke-bot.yml"


def test_healthy_adapter_smoke_run_is_artifact_only() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    healthy_guard = "if (!actionable) {"
    create_call = "await github.rest.issues.create({"

    assert "id: smoke" in workflow
    assert '"zero_signal_issue_creation": False' in workflow
    assert "build/adapter-smoke-policy.json" in workflow
    assert "ACTIONABLE: ${{ steps.smoke.outputs.actionable }}" in workflow
    assert healthy_guard in workflow
    assert "adapter smoke healthy; artifacts uploaded; no issue created" in workflow
    assert "return;" in workflow[workflow.index(healthy_guard) : workflow.rindex(create_call)]
    assert workflow.index(healthy_guard) < workflow.rindex(create_call)


def test_adapter_smoke_uses_one_bot_managed_rolling_tracker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "const rollingTitle = '📣 Adapter smoke follow-up';" in workflow
    assert "const generatedBodyMarker = '<!-- sdetkit:adapter-smoke-tracker:v1 -->';" in workflow
    assert "issue.user?.login === 'github-actions[bot]'" in workflow
    assert "issue.title.startsWith('📣 Adapter smoke pack')" in workflow
    assert "state_reason: 'completed'" in workflow
    assert "const weekOf" not in workflow
    assert "priority:medium" in workflow


def test_adapter_smoke_requires_complete_worker_evidence_before_opening_tracker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'status != "ok"' in workflow
    assert 'required_artifacts = {"adapter-smoke.json", "adapter-tests.log", "bundle.tar"}' in workflow
    assert "missing_required = sorted(required_artifacts - artifact_names)" in workflow
    assert "actionable = bool(actionable_reasons)" in workflow
    assert '"issue_policy": "rolling_tracker_when_actionable"' in workflow
