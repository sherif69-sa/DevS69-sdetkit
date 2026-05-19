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
    permissions = text.split("jobs:", 1)[0]

    assert "contents: write" in permissions
    assert "issues: write" in permissions
    assert "pull-requests: write" in permissions
    assert "checks: read" in permissions
    assert "actions: read" in permissions


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
    assert "build/pr-quality/pr-comment-metadata.json" in text
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
    assert "readCommentMetadata" in text
    assert "action_report_status: metadata.status || 'unknown'" in text
    assert "comment_result_title: metadata.result_title || 'unknown'" in text
    assert "evidence_signal_kind: metadata.evidence_signal_kind || 'unknown'" in text
    assert "evidence_signal_present: Boolean(metadata.evidence_signal_present)" in text
    assert "evidence_review_required: Boolean(metadata.evidence_review_required)" in text


def test_pr_quality_comment_workflow_fails_loud_when_comment_not_visible() -> None:
    text = _workflow_text()

    assert "Verify PR Quality comment visibility" in text
    assert "if: always()" in text
    assert "comment_status=missing" in text
    assert 'status not in {"posted", "updated"}' in text
    assert "PR Quality comment was not posted or updated" in text


def test_pr_quality_comment_workflow_logs_final_comment_signal_state() -> None:
    text = _workflow_text()

    assert "action_report_status = str(payload.get(" in text
    assert "comment_result_title = str(payload.get(" in text
    assert "evidence_signal_kind = str(payload.get(" in text
    assert "evidence_signal_present = bool(payload.get(" in text
    assert "evidence_review_required = bool(payload.get(" in text
    assert 'print(f"action_report_status={action_report_status}")' in text
    assert 'print(f"comment_result_title={comment_result_title}")' in text
    assert 'print(f"evidence_signal_kind={evidence_signal_kind}")' in text
    assert 'print(f"evidence_signal_present={str(evidence_signal_present).lower()}")' in text
    assert 'print(f"evidence_review_required={str(evidence_review_required).lower()}")' in text


def test_pr_quality_comment_workflow_requires_final_comment_signal_metadata() -> None:
    text = _workflow_text()

    assert "PR Quality comment signal metadata missing: action_report_status=unknown" in text
    assert "PR Quality comment signal metadata missing: comment_result_title=unknown" in text
    assert 'evidence_signal_kind not in {"none", "proof", "review"}' in text
    assert "PR Quality comment signal metadata invalid: " in text


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
    assert "--json-out build/pr-quality/pr-evidence-narrative.json" in text
    assert "python -m sdetkit.pr_quality_action_report" in text
    assert "--action-report build/pr-quality/check-intelligence/action-report.json" in text
    assert (
        "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in text
    )
    assert "--evidence-narrative build/pr-quality/pr-evidence-narrative.json" in text
    assert "--out build/pr-quality/pr-comment-body.md" in text
    assert "> build/pr-quality/pr-comment-metadata.json" in text


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


def test_pr_quality_comment_workflow_persists_required_contexts_for_missing_status_detection() -> (
    None
):
    text = _workflow_text()

    assert '"required_contexts": sorted(required_contexts)' in text
    assert "required-contexts.json" in text
    assert "combined-status-raw.json" in text


def test_pr_quality_comment_workflow_feeds_action_report_into_evidence_graph() -> None:
    text = _workflow_text()

    check_intelligence_step = text.index("Build PR check intelligence action report")
    graph_step = text.index("Build PR evidence graph")
    narrative_step = text.index("python -m sdetkit.pr_quality_evidence_narrative")

    assert check_intelligence_step < graph_step < narrative_step
    assert "python -m sdetkit.evidence_graph" in text
    assert (
        "--pr-quality-action-report build/pr-quality/check-intelligence/action-report.json" in text
    )
    assert (
        "--sentinel-control-room build/sdetkit/sentinel/control-room-with-security-review.json"
        in text
    )
    assert "--failure-bundle build/pr-quality/failure-intelligence/failure-bundle.json" in text


def test_pr_quality_comment_workflow_passes_evidence_narrative_into_final_comment() -> None:
    text = _workflow_text()

    narrative_step = text.index("python -m sdetkit.pr_quality_evidence_narrative")
    narrative_json = text.index("--json-out build/pr-quality/pr-evidence-narrative.json")
    action_report_step = text.index("python -m sdetkit.pr_quality_action_report")
    evidence_arg = text.index("--evidence-narrative build/pr-quality/pr-evidence-narrative.json")
    comment_out = text.index("--out build/pr-quality/pr-comment-body.md")

    assert narrative_step < narrative_json < action_report_step
    assert action_report_step < evidence_arg < comment_out


def test_pr_quality_workflow_runs_safe_formatting_autopilot_bridge() -> None:
    text = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")

    check_intelligence = text.index("python -m sdetkit.check_intelligence")
    bridge = text.index("Commit approved safe formatting fixes")
    narrative = text.index("--out build/pr-quality/pr-evidence-narrative.md")

    assert check_intelligence < bridge < narrative
    assert "tools/maintenance_autopilot.py" in text
    assert "--commit-safe-fixes" in text
    assert (
        "--check-intelligence-json build/pr-quality/check-intelligence/check-intelligence.json"
        in text
    )
    assert "--pr-quality-safe-bridge-only" in text
    assert "--out-dir build/pr-quality/safe-formatting-autopilot" in text
    assert "build/pr-quality/safe-formatting-autopilot/" in text


def test_pr_quality_workflow_grants_contents_write_for_safe_branch_commit() -> None:
    text = Path(".github/workflows/pr-quality-comment.yml").read_text(encoding="utf-8")
    permissions = text.split("jobs:", 1)[0]

    assert "permissions:" in permissions
    assert "contents: write" in permissions


def test_pr_quality_workflow_uploads_safe_fix_outcome_artifacts() -> None:
    text = _workflow_text()

    assert "build/pr-quality/safe-formatting-autopilot/" in text
    assert "Commit approved safe formatting fixes" in text
    assert "Build PR comment body" in text
    assert text.index("Commit approved safe formatting fixes") < text.index("Build PR comment body")
