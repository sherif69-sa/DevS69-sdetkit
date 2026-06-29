from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ghas-campaign-bot.yml"
PLAN_PATH = ROOT / "docs" / "contracts" / "workflow-consolidation-plan.v1.json"


def test_ghas_campaign_does_not_create_zero_signal_issue() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    guard = "if (!actionableFindings && alertFetchFailures.length === 0)"
    notice = "no actionable open alerts; no issue created"
    create_call = "await github.rest.issues.create({"

    assert "const alertFetchFailures = [];" in workflow
    assert guard in workflow
    assert notice in workflow
    assert workflow.index(guard) < workflow.rindex(create_call)
    assert "return;" in workflow[workflow.index(guard) : workflow.rindex(create_call)]


def test_ghas_campaign_preserves_unknown_evidence_for_review() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "alertFetchFailures.push(message);" in workflow
    assert "alertFetchFailures.length === 0" in workflow


def test_workflow_consolidation_contract_tracks_current_topology_and_policy() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    assert plan["current_workflow_count"] == 56
    assert plan["target_primary_workflow_count"] == 12
    assert len(plan["keep_primary"]) == 12
    assert plan["zero_signal_issue_policy"] == {
        "create_issue_when_actionable_finding_count_is_zero": False,
        "close_existing_tracker_when_findings_reach_zero": True,
        "preserve_issue_when_source_evidence_is_unavailable": True,
        "first_enforced_workflow": "ghas-campaign-bot.yml",
    }
    assert plan["success_targets"]["zero_signal_generated_issues"] == 0
    assert plan["success_targets"]["required_check_compatibility_preserved"] is True
