from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")
QUALITY_LOG = "/".join(("build", "pr-quality", "failure-intelligence", "quality.log"))


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_workflow_uses_failure_bundle_handoff() -> None:
    text = _workflow_text()

    assert "Build adaptive failure intelligence bundle" in text
    assert "python -m sdetkit adaptive failure-bundle" in text
    assert f"--log {QUALITY_LOG}" in text
    assert f"tee {QUALITY_LOG}" in text
    assert "tee quality.log" not in text
    assert "--out-dir build/pr-quality/failure-intelligence" in text
    assert "--proof-failed" in text

    assert "python -m sdetkit.adaptive_diagnosis" not in text
    assert "python -m sdetkit.pr_quality_comment" not in text


def test_pr_quality_workflow_passes_failure_bundle_to_adaptive_renderer() -> None:
    text = _workflow_text()

    assert "--failure-bundle build/pr-quality/failure-intelligence/failure-bundle.json" in text
    assert "python -m sdetkit.pr_quality_evidence_narrative" in text
    assert "build/pr-quality/adaptive-diagnosis-comment.md" not in text


def test_pr_quality_workflow_uploads_failure_intelligence_bundle() -> None:
    text = _workflow_text()

    assert "Upload failure intelligence bundle" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text
    assert "name: pr-quality-failure-intelligence" in text
    assert "path: build/pr-quality/failure-intelligence/" in text
    assert "if-no-files-found: ignore" in text


def test_pr_quality_workflow_sets_failure_bundle_proof_from_quality_outcome() -> None:
    text = _workflow_text()

    assert 'proof_flag="--proof-failed"' in text
    assert 'proof_flag="--proof-passed"' in text
    assert "steps.quality.outcome" in text


def test_pr_quality_workflow_does_not_inline_adaptive_comment_logic() -> None:
    text = _workflow_text()

    assert "append_adaptive_diagnosis_comment" not in text
    assert "adaptive-diagnosis-comment.md" not in text
    assert "cat build/pr-quality/failure-intelligence" not in text
