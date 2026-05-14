from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_workflow_runs_adaptive_sentinel_after_failure_bundle() -> None:
    text = _workflow_text()

    assert "Build adaptive failure intelligence bundle" in text
    assert "Run adaptive sentinel scan" in text
    assert text.index("Build adaptive failure intelligence bundle") < text.index(
        "Run adaptive sentinel scan"
    )
    assert "python -m sdetkit adaptive sentinel scan" in text
    assert "--out-dir build/sdetkit/sentinel" in text
    assert "--no-fail" in text


def test_pr_quality_workflow_comments_warning_or_critical_sentinel_summary() -> None:
    text = _workflow_text()

    assert 'sentinel_state="unknown"' in text
    assert 'sentinel_state" = "warning"' in text
    assert 'sentinel_state" = "critical"' in text
    assert "### Adaptive Sentinel" in text
    assert "build/sdetkit/sentinel/sentinel.json" in text
    assert "build/sdetkit/sentinel/sentinel.md" in text
    assert "Recommended next commands" in text
    assert text.count("append_sentinel_summary") >= 3


def test_pr_quality_workflow_uploads_adaptive_sentinel_artifacts() -> None:
    text = _workflow_text()

    assert "Upload adaptive sentinel artifacts" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "name: pr-quality-adaptive-sentinel" in text
    assert "build/sdetkit/sentinel/" in text
    assert ".sdetkit/adaptive-sentinel/" in text


def test_pr_quality_workflow_builds_evidence_graph_from_sentinel_control_room() -> None:
    text = _workflow_text()

    assert "Build PR evidence graph" in text
    assert "python -m sdetkit.evidence_graph" in text
    assert "--sentinel-control-room build/sdetkit/sentinel/control-room.json" in text
    assert "--out-dir build/sdetkit/evidence-graph" in text
    assert "### Evidence Graph" in text
    assert "build/sdetkit/evidence-graph/evidence-graph.json" in text
    assert "build/sdetkit/evidence-graph/evidence-graph.md" in text


def test_pr_quality_workflow_uploads_evidence_graph_artifacts() -> None:
    text = _workflow_text()

    assert "build/sdetkit/evidence-graph/" in text
