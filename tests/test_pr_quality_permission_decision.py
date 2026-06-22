from pathlib import Path

DECISION = Path("docs/ci/workflow-permission-decisions/pr-quality-trusted-publisher.md")


def test_pr_quality_publisher_permission_decision_is_scoped_and_human_reviewed() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "reviewer=sherif69-sa" in text
    assert "decision=approved_scoped_permission_move" in text
    assert "source_workflow=.github/workflows/pr-quality-comment.yml" in text
    assert "publisher_workflow=.github/workflows/pr-quality-publisher.yml" in text
    assert 'publisher_write_scopes=["issues: write", "pull-requests: write"]' in text
    assert "publisher_checkout_allowed=false" in text
    assert "publisher_repository_code_execution_allowed=false" in text
    assert "remaining_group_workflows_pending=true" in text
