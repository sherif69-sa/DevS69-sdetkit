from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def test_pr_quality_workflow_feeds_failure_bundle_into_evidence_graph() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    command_index = text.index("sdetkit.evidence_graph")
    next_step_index = text.find("      - name:", command_index + 1)
    if next_step_index == -1:
        next_step_index = len(text)
    graph_command = text[command_index:next_step_index]

    assert (
        "--failure-bundle build/pr-quality/failure-intelligence/failure-bundle.json"
        in graph_command
    )
    assert "--out-dir build/sdetkit/evidence-graph" in graph_command
    assert "sdetkit.pr_quality_evidence_narrative" not in graph_command
