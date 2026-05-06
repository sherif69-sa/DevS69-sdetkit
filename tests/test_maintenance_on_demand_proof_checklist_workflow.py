from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_proof_checklist_after_action_categories():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance proof checklist" in text
    assert "python -m sdetkit.maintenance_proof_checklist" in text
    assert "if [ -f artifacts/maintenance-action-categories.json ]; then" in text
    assert "--action-categories-json artifacts/maintenance-action-categories.json" in text
    assert "--out-json artifacts/maintenance-proof-checklist.json" in text
    assert "--out-md artifacts/maintenance-proof-checklist.md" in text
    assert text.index("Build maintenance action categories") < text.index(
        "Build maintenance proof checklist"
    )
    assert text.index("Build maintenance proof checklist") < text.index(
        "Record maintenance policy decision history"
    )


def test_maintenance_on_demand_uploads_proof_checklist_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-proof-checklist.json" in text
    assert "artifacts/maintenance-proof-checklist.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_proof_checklist_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const proofChecklistMd = fs.existsSync('artifacts/maintenance-proof-checklist.md')" in text
    assert "### Maintenance proof checklist" in text
    assert "proofChecklistMd.length > 3000" in text


def test_proof_checklist_appears_before_action_categories_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance proof checklist") < text.index(
        "### Maintenance action categories"
    )
