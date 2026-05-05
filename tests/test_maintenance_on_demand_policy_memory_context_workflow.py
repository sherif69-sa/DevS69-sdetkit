from pathlib import Path

WORKFLOW = Path(".github/workflows/maintenance-on-demand.yml")


def test_maintenance_on_demand_builds_policy_memory_context_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Build maintenance policy memory context" in text
    assert "python -m sdetkit.maintenance_policy_memory_context" in text
    assert "--policy-decisions-json artifacts/maintenance-policy-decisions.json" in text
    assert "--safe-fix-rollup-json artifacts/adaptive-safe-fix-learning-rollup.json" in text
    assert "--annotation-report-json artifacts/annotation-hygiene-report.json" in text
    assert "--history-jsonl artifacts/maintenance-policy-decisions-history.jsonl" in text
    assert "--out-json artifacts/maintenance-policy-memory-context.json" in text
    assert "--out-md artifacts/maintenance-policy-memory-context.md" in text


def test_maintenance_on_demand_uploads_policy_memory_context_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/maintenance-policy-memory-context.json" in text
    assert "artifacts/maintenance-policy-memory-context.md" in text
    assert "if-no-files-found: ignore" in text


def test_maintenance_issue_comment_includes_policy_memory_context_when_present():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "const memoryContextMd = fs.existsSync('artifacts/maintenance-policy-memory-context.md')"
        in text
    )
    assert "### Maintenance policy memory context" in text
    assert "memoryContextMd.length > 3000" in text


def test_policy_memory_context_appears_before_policy_decisions_in_issue_comment():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert text.index("### Maintenance policy memory context") < text.index(
        "### Maintenance policy decisions"
    )
