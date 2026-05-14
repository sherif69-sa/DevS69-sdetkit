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


def test_pr_quality_workflow_sets_failure_bundle_proof_from_quality_outcome() -> None:
    text = _workflow_text()

    assert 'proof_flag="--proof-failed"' in text
    assert 'proof_flag="--proof-passed"' in text
    assert "steps.quality.outcome" in text


def test_pr_quality_success_comment_does_not_reprint_adaptive_diagnosis() -> None:
    text = _workflow_text()
    comment_body = text.split("write_evidence_graph_summary", 1)[1]
    success_block = comment_body.split(
        'if [ "${{ steps.quality.outcome }}" = "success" ]; then',
        1,
    )[1].split("else", 1)[0]

    assert "adaptive-diagnosis-comment.md" not in success_block
    assert "append_adaptive_diagnosis_comment" not in success_block
