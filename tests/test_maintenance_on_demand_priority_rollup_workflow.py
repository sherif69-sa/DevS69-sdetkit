from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_priority_rollup_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance priority rollup" in text
    assert "python -m sdetkit.maintenance_priority_rollup" in text
    assert "--maintenance-json artifacts/maintenance.json" in text
    assert "--annotation-report-json artifacts/annotation-hygiene-report.json" in text
    assert "--safe-fix-rollup-json artifacts/adaptive-safe-fix-learning-rollup.json" in text
    assert "--out-json artifacts/maintenance-priority-rollup.json" in text
    assert "--out-md artifacts/maintenance-priority-rollup.md" in text


def test_maintenance_on_demand_uploads_priority_rollup_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-priority-rollup.json" in text
    assert "artifacts/maintenance-priority-rollup.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_priority_rollup_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const priorityMd = fs.existsSync('artifacts/maintenance-priority-rollup.md')" in text
    assert "### Maintenance priority rollup" in text
    assert "priorityMd.length > 3000" in text
