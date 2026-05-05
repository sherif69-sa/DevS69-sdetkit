from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_records_policy_decision_history():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Record maintenance policy decision history" in text
    assert "python -m sdetkit.maintenance_policy_decision_history" in text
    assert "--policy-decisions-json artifacts/maintenance-policy-decisions.json" in text
    assert "--memory-context-json artifacts/maintenance-policy-memory-context.json" in text
    assert "--history-jsonl artifacts/maintenance-policy-decisions-history.jsonl" in text
    assert '--run-id "${GITHUB_RUN_ID}"' in text
    assert "--out-json artifacts/maintenance-policy-decision-history-summary.json" in text
    assert "--out-md artifacts/maintenance-policy-decision-history-summary.md" in text


def test_maintenance_on_demand_uploads_policy_history_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-policy-decisions-history.jsonl" in text
    assert "artifacts/maintenance-policy-decision-history-summary.json" in text
    assert "artifacts/maintenance-policy-decision-history-summary.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_policy_history_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "const historyMd = fs.existsSync('artifacts/maintenance-policy-decision-history-summary.md')"
        in text
    )
    assert "### Maintenance policy decision history" in text
    assert "historyMd.length > 3000" in text


def test_policy_history_appears_before_memory_context_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance policy decision history") < text.index(
        "### Maintenance policy memory context"
    )
