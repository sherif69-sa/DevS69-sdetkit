from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_restores_policy_history_before_memory_context():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Restore maintenance policy decision history" in text
    assert ".sdetkit/maintenance/policy-decisions-history.jsonl" in text
    assert "artifacts/maintenance-policy-decisions-history.jsonl" in text
    assert text.index("Restore maintenance policy decision history") < text.index(
        "Build maintenance policy memory context"
    )


def test_maintenance_on_demand_persists_policy_history_after_recording():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Persist maintenance policy decision history" in text
    assert (
        "cp artifacts/maintenance-policy-decisions-history.jsonl "
        ".sdetkit/maintenance/policy-decisions-history.jsonl"
    ) in text
    assert text.index("Record maintenance policy decision history") < text.index(
        "Persist maintenance policy decision history"
    )
    assert text.index("Persist maintenance policy decision history") < text.index(
        "Upload artifacts"
    )


def test_maintenance_on_demand_uploads_policy_history_store_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert ".sdetkit/maintenance/policy-decisions-history.jsonl" in text
    assert "artifacts/maintenance-policy-decisions-history.jsonl" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_pr_summary_mentions_policy_memory_persistence():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "### Policy memory" in text
    assert "policy-decisions-history.jsonl` is included when policy history changes" in text
