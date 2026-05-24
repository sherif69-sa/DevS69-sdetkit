from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_builds_security_diagnosis_after_collecting_security_inputs() -> None:
    text = _workflow_text()

    assert "Collect security review evidence" in text
    assert "Collect code scanning alert evidence" in text
    assert "Diagnose security findings read-only" in text
    assert text.index("Collect code scanning alert evidence") < text.index(
        "Diagnose security findings read-only"
    )
    assert text.index("Diagnose security findings read-only") < text.index(
        "Build PR check intelligence action report"
    )
    assert "python -m sdetkit.security_finding_diagnosis" in text
    assert "--review-threads-json build/pr-quality/security-review/review-threads.json" in text
    assert "--code-scanning-alerts-json build/pr-quality/code-scanning/alerts.json" in text
    assert '--current-head-sha "$HEAD_SHA"' in text
    assert "--root ." in text


def test_pr_quality_uploads_security_diagnosis_artifact_without_automation() -> None:
    text = _workflow_text()

    assert "build/pr-quality/security-diagnosis/" in text
    diagnosis_block = text.split("- name: Diagnose security findings read-only", 1)[1].split(
        "- name: Build PR check intelligence action report", 1
    )[0]
    assert "dismiss" not in diagnosis_block.lower()
    assert "commit-safe-fixes" not in diagnosis_block


def test_pr_quality_passes_security_diagnosis_artifact_to_operator_comment_renderer() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.pr_quality_action_report" in text
    assert (
        "--security-finding-diagnosis build/pr-quality/security-diagnosis/security-finding-diagnosis.json"
        in text
    )
    assert text.index("Diagnose security findings read-only") < text.index(
        "python -m sdetkit.pr_quality_action_report"
    )
