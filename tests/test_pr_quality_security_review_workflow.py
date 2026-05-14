from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def test_pr_quality_workflow_collects_security_review_threads_before_graph() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Collect security review evidence" in text
    assert "gh api graphql" in text
    assert "reviewThreads(first: 100)" in text
    assert "python -m sdetkit.security_review_evidence" in text
    assert "build/pr-quality/security-review/review-threads.json" in text
    assert "build/sdetkit/sentinel/control-room-with-security-review.json" in text

    collect_index = text.index("Collect security review evidence")
    graph_index = text.index("Build PR evidence graph")
    assert collect_index < graph_index


def test_pr_quality_workflow_builds_graph_from_security_merged_control_room() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "--sentinel-control-room build/sdetkit/sentinel/control-room-with-security-review.json"
        in text
    )
