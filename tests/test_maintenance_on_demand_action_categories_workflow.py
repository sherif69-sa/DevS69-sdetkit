from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_action_categories_after_action_plan():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance action categories" in text
    assert "python -m sdetkit.maintenance_action_categories" in text
    assert "if [ -f artifacts/maintenance-action-plan.json ]; then" in text
    assert "--action-plan-json artifacts/maintenance-action-plan.json" in text
    assert "--out-json artifacts/maintenance-action-categories.json" in text
    assert "--out-md artifacts/maintenance-action-categories.md" in text
    assert text.index("Build maintenance action plan") < text.index(
        "Build maintenance action categories"
    )
    assert text.index("Build maintenance action categories") < text.index(
        "Record maintenance policy decision history"
    )


def test_maintenance_on_demand_uploads_action_category_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-action-categories.json" in text
    assert "artifacts/maintenance-action-categories.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_action_categories_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "const actionCategoriesMd = fs.existsSync('artifacts/maintenance-action-categories.md')"
        in text
    )
    assert "### Maintenance action categories" in text
    assert "actionCategoriesMd.length > 3000" in text


def test_action_categories_appear_before_action_plan_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance action categories") < text.index(
        "### Maintenance action plan"
    )
