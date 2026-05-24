from __future__ import annotations

from pathlib import Path


def test_pr_quality_workflow_collects_failed_check_logs_before_check_intelligence() -> None:
    workflow = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")

    assert "python -m sdetkit.failed_check_log_collection" in workflow
    assert "--checks-json build/pr-quality/checks/check-runs.json" in workflow
    assert "--out-dir build/pr-quality/check-logs" in workflow
    assert "bash build/pr-quality/check-logs/download-failed-check-logs.sh || true" in workflow
    assert "--logs-dir build/pr-quality/check-logs/failed-check-logs" in workflow

    first_collection = workflow.index("python -m sdetkit.failed_check_log_collection")
    intelligence = workflow.index("python -m sdetkit.check_intelligence")
    assert first_collection < intelligence


def test_pr_quality_workflow_uploads_failed_check_log_artifacts() -> None:
    workflow = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")

    assert "build/pr-quality/check-logs/" in workflow
    assert "build/pr-quality/check-intelligence/" in workflow


def test_pr_quality_existing_collector_invocation_carries_check_annotation_evidence_to_intelligence() -> (
    None
):
    workflow = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")

    assert "checks: read" in workflow
    assert "python -m sdetkit.failed_check_log_collection" in workflow
    assert "bash build/pr-quality/check-logs/download-failed-check-logs.sh || true" in workflow
    assert "--logs-dir build/pr-quality/check-logs/failed-check-logs" in workflow
    assert workflow.index(
        "bash build/pr-quality/check-logs/download-failed-check-logs.sh"
    ) < workflow.index("python -m sdetkit.check_intelligence")
