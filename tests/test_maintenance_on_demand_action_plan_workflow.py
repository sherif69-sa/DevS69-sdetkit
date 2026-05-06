from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_action_plan_after_eligibility():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance action plan" in text
    assert "python -m sdetkit.maintenance_action_plan" in text
    assert "if [ -f artifacts/maintenance-recommendation-eligibility.json ]; then" in text
    assert "--eligibility-json artifacts/maintenance-recommendation-eligibility.json" in text
    assert "--out-json artifacts/maintenance-action-plan.json" in text
    assert "--out-md artifacts/maintenance-action-plan.md" in text
    assert text.index("Build maintenance recommendation eligibility") < text.index(
        "Build maintenance action plan"
    )
    assert text.index("Build maintenance action plan") < text.index(
        "Record maintenance policy decision history"
    )


def test_maintenance_on_demand_uploads_action_plan_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-action-plan.json" in text
    assert "artifacts/maintenance-action-plan.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_action_plan_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const actionPlanMd = fs.existsSync('artifacts/maintenance-action-plan.md')" in text
    assert "### Maintenance action plan" in text
    assert "actionPlanMd.length > 3000" in text


def test_action_plan_appears_before_eligibility_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance action plan") < text.index(
        "### Maintenance recommendation eligibility"
    )
