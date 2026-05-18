from __future__ import annotations

from pathlib import Path


def test_pr_quality_workflow_publishes_verified_operator_loop() -> None:
    workflow = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")

    assert "Build verified operator evidence loop" in workflow
    assert "python -m sdetkit operator-loop" in workflow
    assert "--verify" in workflow
    assert "--quality-log quality.log" in workflow
    assert '--quality-outcome "${{ steps.quality.outcome }}"' in workflow
    assert "--evidence-graph build/sdetkit/evidence-graph/evidence-graph.json" in workflow
    assert "--failure-bundle build/pr-quality/failure-intelligence/failure-bundle.json" in workflow
    assert "--action-report build/pr-quality/check-intelligence/action-report.json" in workflow
    assert "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in workflow
    assert "--out-dir build/sdetkit/operator-loop" in workflow
    assert "> build/sdetkit/operator-loop/operator-loop-stdout.json" in workflow
    assert "build/sdetkit/operator-loop/" in workflow


def test_pr_quality_workflow_builds_operator_loop_after_pr_comment_body() -> None:
    workflow = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")

    comment_body_index = workflow.index("Build PR comment body")
    operator_loop_index = workflow.index("Build verified operator evidence loop")
    upload_index = workflow.index("Upload PR quality comment artifacts")

    assert comment_body_index < operator_loop_index < upload_index
