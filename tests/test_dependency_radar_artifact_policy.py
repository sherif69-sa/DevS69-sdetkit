from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dependency-radar-bot.yml"


def test_zero_actionable_dependency_run_is_artifact_only() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    healthy_guard = "if (!actionable) {"
    create_call = "await github.rest.issues.create({"

    assert "id: radar" in workflow
    assert "build/dependency-radar-policy.json" in workflow
    assert "ACTIONABLE: ${{ steps.radar.outputs.actionable }}" in workflow
    assert '"zero_finding_issue_creation": False' in workflow
    assert healthy_guard in workflow
    assert "dependency radar has zero actionable packages; artifacts uploaded" in workflow
    assert "return;" in workflow[workflow.index(healthy_guard) : workflow.rindex(create_call)]
    assert workflow.index(healthy_guard) < workflow.rindex(create_call)


def test_dependency_radar_uses_one_bot_managed_rolling_tracker() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "const rollingTitle = '📡 Dependency radar follow-up';" in workflow
    assert (
        "const generatedBodyMarker = '<!-- sdetkit:dependency-radar-tracker:v1 -->';"
        in workflow
    )
    assert "issue.user?.login === 'github-actions[bot]'" in workflow
    assert "issue.title.startsWith('📡 Dependency radar + runtime watchlist')" in workflow
    assert "state_reason: 'completed'" in workflow
    assert "const weekOf" not in workflow


def test_dependency_radar_fails_closed_on_malformed_audit_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "evidence_available = isinstance(packages_raw, list)" in workflow
    assert "actionable_count_valid = isinstance(actionable_value, int)" in workflow
    assert "dependency audit evidence unavailable or malformed" in workflow
    assert "actionable package count unavailable or malformed" in workflow
    assert "actionable = bool(actionable_reasons)" in workflow
    assert '"issue_policy": "rolling_tracker_when_actionable"' in workflow


def test_only_positive_actionable_count_creates_dependency_follow_up() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "if actionable_count > 0:" in workflow
    assert 'actionable_reasons.append(f"actionable dependency packages: {actionable_count}")' in workflow
    assert "No issue is created when the audit reports zero actionable packages." in workflow
