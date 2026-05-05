from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_annotation_hygiene_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build annotation hygiene report" in text
    assert "python -m sdetkit.github_actions_annotation_hygiene_report" in text
    assert "--maintenance-json artifacts/maintenance.json" in text
    assert "--out-json artifacts/annotation-hygiene-report.json" in text
    assert "--out-md artifacts/annotation-hygiene-report.md" in text


def test_maintenance_on_demand_uploads_annotation_hygiene_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/annotation-hygiene-report.json" in text
    assert "artifacts/annotation-hygiene-report.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_annotation_hygiene_report_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const annotationMd = fs.existsSync('artifacts/annotation-hygiene-report.md')" in text
    assert "### GitHub Actions annotation hygiene" in text
    assert "annotationMd.length > 3000" in text
