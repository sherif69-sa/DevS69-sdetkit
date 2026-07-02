from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "workflow-governance-bot.yml"
SCRIPT = ROOT / "scripts" / "build_workflow_governance_policy.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("build_workflow_governance_policy", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _healthy_audit() -> dict[str, object]:
    return {
        "summary": {
            "workflow_count": 57,
            "missing_permissions": [],
            "unpinned_uses": [],
            "missing_dispatch": [],
            "pr_target": [],
        },
        "finding_count": 0,
        "findings": [],
    }


def test_zero_finding_workflow_governance_run_is_artifact_only() -> None:
    module = _load_script()
    policy, markdown = module.build_policy_and_markdown(_healthy_audit())

    assert policy["actionable"] is False
    assert policy["workflow_finding_count"] == 0
    assert policy["zero_finding_issue_creation"] is False
    assert policy["actionable_reasons"] == []
    assert "No issue is created when the audit reports zero actionable findings." in markdown


def test_workflow_governance_fails_closed_on_malformed_evidence() -> None:
    module = _load_script()
    policy, _markdown = module.build_policy_and_markdown({})

    assert policy["actionable"] is True
    assert policy["evidence_available"] is False
    assert policy["finding_count_valid"] is False
    assert policy["actionable_reasons"] == [
        "workflow governance audit evidence unavailable or malformed",
        "workflow governance finding count unavailable or malformed",
    ]


def test_positive_workflow_governance_findings_require_follow_up() -> None:
    module = _load_script()
    audit = _healthy_audit()
    audit["finding_count"] = 1
    audit["findings"] = [
        {"type": "missing_permissions", "workflow": "example.yml"},
    ]
    summary = audit["summary"]
    assert isinstance(summary, dict)
    summary["missing_permissions"] = ["example.yml"]

    policy, markdown = module.build_policy_and_markdown(audit)

    assert policy["actionable"] is True
    assert policy["workflow_finding_count"] == 1
    assert policy["actionable_reasons"] == ["workflow governance findings: 1"]
    assert "A single rolling tracker is created or refreshed" in markdown


def test_workflow_uses_one_bot_managed_tracker_and_stays_below_heavy_budget() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    healthy_guard = "if (!actionable) {"
    create_call = "await github.rest.issues.create({"

    assert len(workflow.splitlines()) < 250
    assert "python scripts/build_workflow_governance_policy.py" in workflow
    assert "ACTIONABLE: ${{ steps.governance.outputs.actionable }}" in workflow
    assert "const rollingTitle = '🧾 Workflow governance follow-up';" in workflow
    assert (
        "const generatedBodyMarker = '<!-- sdetkit:workflow-governance-tracker:v1 -->';"
        in workflow
    )
    assert "issue.user?.login === 'github-actions[bot]'" in workflow
    assert "issue.title.startsWith('🧾 Workflow governance audit')" in workflow
    assert "state_reason: 'completed'" in workflow
    assert "const monthOf" not in workflow
    assert healthy_guard in workflow
    assert "return;" in workflow[workflow.index(healthy_guard) : workflow.rindex(create_call)]
    assert workflow.index(healthy_guard) < workflow.rindex(create_call)
