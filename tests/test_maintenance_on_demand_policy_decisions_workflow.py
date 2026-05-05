from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_policy_decision_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance policy decisions" in text
    assert "python -m sdetkit.maintenance_policy_decisions" in text
    assert "--priority-rollup-json artifacts/maintenance-priority-rollup.json" in text
    assert "--out-json artifacts/maintenance-policy-decisions.json" in text
    assert "--out-md artifacts/maintenance-policy-decisions.md" in text


def test_maintenance_on_demand_uploads_policy_decision_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-policy-decisions.json" in text
    assert "artifacts/maintenance-policy-decisions.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_policy_decisions_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const policyMd = fs.existsSync('artifacts/maintenance-policy-decisions.md')" in text
    assert "### Maintenance policy decisions" in text
    assert "policyMd.length > 3000" in text


def test_policy_decisions_appear_before_priority_rollup_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance policy decisions") < text.index(
        "### Maintenance priority rollup"
    )
