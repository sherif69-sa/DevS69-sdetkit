from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_comment_workflow_has_queue_safe_concurrency_and_timeout() -> None:
    text = _workflow_text()

    assert "name: PR Quality Comment" in text
    assert "pull_request:" in text
    assert "concurrency:" in text
    assert "group: pr-quality-comment-${{ github.event.pull_request.number }}" in text
    assert "cancel-in-progress: true" in text
    assert "timeout-minutes: 20" in text


def test_pr_quality_comment_workflow_has_comment_permissions() -> None:
    text = _workflow_text()

    assert "contents: read" in text
    assert "pull-requests: write" in text
    assert "issues: write" in text


def test_pr_quality_comment_workflow_writes_comment_status_before_posting() -> None:
    text = _workflow_text()

    assert "Initialize PR comment status" in text
    assert "build/pr-quality/comment-status.json" in text
    assert '"status": "failed"' in text
    assert '"reason": "comment step did not complete"' in text


def test_pr_quality_comment_workflow_uploads_comment_artifacts() -> None:
    text = _workflow_text()

    assert "Upload PR quality comment artifacts" in text
    assert "build/pr-quality/pr-comment-body.md" in text
    assert "build/pr-quality/pr-evidence-narrative.json" in text
    assert "build/pr-quality/changed-files.txt" in text
    assert "build/pr-quality/comment-status.json" in text
    assert "build/sdetkit/evidence-graph/" in text


def test_pr_quality_comment_workflow_updates_or_posts_comment_and_records_status() -> None:
    text = _workflow_text()

    assert "listComments" in text
    assert "updateComment" in text
    assert "createComment" in text
    assert "comment_status=updated" in text
    assert "comment_status=posted" in text
    assert "posted SDET Quality Gate comment" in text
    assert "updated existing SDET Quality Gate comment" in text


def test_pr_quality_comment_workflow_fails_loud_when_comment_not_visible() -> None:
    text = _workflow_text()

    assert "Verify PR Quality comment visibility" in text
    assert "if: always()" in text
    assert "comment_status=missing" in text
    assert 'status not in {"posted", "updated"}' in text
    assert "PR Quality comment was not posted or updated" in text


def test_pr_quality_comment_workflow_builds_check_intelligence_action_report() -> None:
    text = _workflow_text()

    assert "Build PR check intelligence action report" in text
    assert "check-runs?per_page=100" in text
    assert "build/pr-quality/checks/check-runs.json" in text
    assert "PR Quality local quality gate" in text
    assert "python -m sdetkit.check_intelligence" in text
    assert "--review-threads-json build/pr-quality/security-review/review-threads.json" in text
    assert "--out-dir build/pr-quality/check-intelligence" in text


def test_pr_quality_comment_workflow_renders_comment_from_action_report() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.pr_quality_evidence_narrative" in text
    assert "--out build/pr-quality/pr-evidence-narrative.md" in text
    assert "python -m sdetkit.pr_quality_action_report" in text
    assert "--action-report build/pr-quality/check-intelligence/action-report.json" in text
    assert (
        "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in text
    )
    assert "--out build/pr-quality/pr-comment-body.md" in text


def test_pr_quality_comment_workflow_uploads_check_intelligence_artifacts() -> None:
    text = _workflow_text()

    assert "build/pr-quality/checks/" in text
    assert "build/pr-quality/check-intelligence/" in text
    assert "build/pr-quality/pr-evidence-narrative.md" in text


def test_pr_quality_comment_workflow_marks_required_contexts_for_check_intelligence() -> None:
    text = _workflow_text()

    assert "required_status_checks/contexts" in text
    assert "combined-status-raw.json" in text
    assert "required-contexts.json" in text
    assert '"required": context in required_contexts' in text
    assert 'item["required"] = name in required_contexts' in text
