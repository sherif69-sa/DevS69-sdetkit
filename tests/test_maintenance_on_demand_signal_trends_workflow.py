from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_signal_trends_after_proof_checklist():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance signal trends" in text
    assert "python -m sdetkit.maintenance_signal_trends" in text
    assert "if [ -f artifacts/maintenance-proof-checklist.json ]; then" in text
    assert "--proof-checklist-json artifacts/maintenance-proof-checklist.json" in text
    assert "--history-jsonl artifacts/maintenance-policy-decisions-history.jsonl" in text
    assert "--out-json artifacts/maintenance-signal-trends.json" in text
    assert "--out-md artifacts/maintenance-signal-trends.md" in text
    assert text.index("Build maintenance proof checklist") < text.index(
        "Build maintenance signal trends"
    )
    assert text.index("Build maintenance signal trends") < text.index(
        "Record maintenance policy decision history"
    )


def test_maintenance_on_demand_uploads_signal_trend_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-signal-trends.json" in text
    assert "artifacts/maintenance-signal-trends.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_signal_trends_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "const signalTrendsMd = fs.existsSync('artifacts/maintenance-signal-trends.md')" in text
    assert "### Maintenance signal trends" in text
    assert "signalTrendsMd.length > 3000" in text


def test_signal_trends_appear_before_proof_checklist_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance signal trends") < text.index(
        "### Maintenance proof checklist"
    )
