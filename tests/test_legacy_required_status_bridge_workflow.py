from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "legacy-required-status-bridge.yml"
)


def test_bridge_workflow_defines_required_legacy_contexts() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: legacy-required-status-bridge" in text
    assert "pull_request:" in text
    assert "workflow_run:" in text
    assert 'workflows: ["CI"]' in text
    assert "statuses: write" in text
    assert "contexts = ['ci', 'maintenance-autopilot']" in text
    assert "state: 'pending'" in text
    assert "state: ciState" in text
    assert "conclusion === 'success' ? 'success' : 'failure'" in text
    assert "createCommitStatus" in text
