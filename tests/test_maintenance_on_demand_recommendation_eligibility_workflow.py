from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_recommendation_eligibility_after_recommendations():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance recommendation eligibility" in text
    assert "python -m sdetkit.maintenance_recommendation_eligibility" in text
    assert "if [ -f artifacts/maintenance-recommendations.json ]; then" in text
    assert "--recommendations-json artifacts/maintenance-recommendations.json" in text
    assert "--out-json artifacts/maintenance-recommendation-eligibility.json" in text
    assert "--out-md artifacts/maintenance-recommendation-eligibility.md" in text
    assert text.index("Build adaptive maintenance recommendations") < text.index(
        "Build maintenance recommendation eligibility"
    )
    assert text.index("Build maintenance recommendation eligibility") < text.index(
        "Record maintenance policy decision history"
    )


def test_maintenance_on_demand_uploads_recommendation_eligibility_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-recommendation-eligibility.json" in text
    assert "artifacts/maintenance-recommendation-eligibility.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_recommendation_eligibility_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "const recommendationEligibilityMd = fs.existsSync"
        "('artifacts/maintenance-recommendation-eligibility.md')"
    ) in text
    assert "### Maintenance recommendation eligibility" in text
    assert "recommendationEligibilityMd.length > 3000" in text


def test_recommendation_eligibility_appears_before_recommendations_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance recommendation eligibility") < text.index(
        "### Adaptive maintenance recommendations"
    )
