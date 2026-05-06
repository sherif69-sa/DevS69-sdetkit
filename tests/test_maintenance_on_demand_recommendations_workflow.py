from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_recommendation_artifacts_after_memory_context():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build adaptive maintenance recommendations" in text
    assert "python -m sdetkit.maintenance_recommendations" in text
    assert "if [ -f artifacts/maintenance-policy-memory-context.json ]; then" in text
    assert "--memory-context-json artifacts/maintenance-policy-memory-context.json" in text
    assert "--out-json artifacts/maintenance-recommendations.json" in text
    assert "--out-md artifacts/maintenance-recommendations.md" in text
    assert text.index("Build maintenance policy memory context") < text.index(
        "Build adaptive maintenance recommendations"
    )
    assert text.index("Build adaptive maintenance recommendations") < text.index(
        "Record maintenance policy decision history"
    )


def test_maintenance_on_demand_uploads_recommendation_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-recommendations.json" in text
    assert "artifacts/maintenance-recommendations.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_recommendations_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "const recommendationsMd = fs.existsSync('artifacts/maintenance-recommendations.md')"
        in text
    )
    assert "### Adaptive maintenance recommendations" in text
    assert "recommendationsMd.length > 3000" in text


def test_recommendations_appear_before_policy_history_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Adaptive maintenance recommendations") < text.index(
        "### Maintenance policy decision history"
    )
