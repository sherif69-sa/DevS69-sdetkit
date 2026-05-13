from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_workflow_uses_failure_bundle_handoff() -> None:
    text = _workflow_text()

    assert "Build adaptive failure intelligence bundle" in text
    assert "python -m sdetkit adaptive failure-bundle" in text
    assert "--log quality.log" in text
    assert "--out-dir build/pr-quality/failure-intelligence" in text
    assert "--proof-failed" in text

    assert "python -m sdetkit.adaptive_diagnosis" not in text
    assert "python -m sdetkit.pr_quality_comment" not in text


def test_pr_quality_workflow_comments_from_bundle_comment_artifact() -> None:
    text = _workflow_text()

    assert "build/pr-quality/failure-intelligence/adaptive-diagnosis-comment.md" in text
    assert "build/pr-quality/adaptive-diagnosis-comment.md" not in text


def test_pr_quality_workflow_uploads_failure_intelligence_bundle() -> None:
    text = _workflow_text()

    assert "Upload failure intelligence bundle" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "name: pr-quality-failure-intelligence" in text
    assert "path: build/pr-quality/failure-intelligence/" in text
    assert "if-no-files-found: ignore" in text
