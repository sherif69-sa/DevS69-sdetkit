from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-lifecycle-reconciliation.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_lifecycle_reconciliation_runs_only_for_merged_or_explicit_recovery_paths() -> None:
    text = _workflow_text()

    assert "name: PR Quality Lifecycle Reconciliation" in text
    assert "pull_request_target:" in text
    assert "types: [closed]" in text
    assert "workflow_dispatch:" in text
    assert "pr_number:" in text
    assert "push:" in text
    assert "branches: [main]" in text
    assert '".github/workflows/pr-quality-lifecycle-reconciliation.yml"' in text
    assert "github.event.pull_request.merged == true" in text
    assert "merged_pull_request_event" in text
    assert "manual_recovery" in text
    assert "trusted_bootstrap_scan" in text


def test_lifecycle_reconciliation_keeps_default_permissions_empty_and_job_scope_narrow() -> None:
    text = _workflow_text()
    workflow_permissions = text.split("jobs:", 1)[0]
    job = text.split("jobs:", 1)[1]

    assert "permissions: {}" in workflow_permissions
    assert "issues: write" in job
    assert "pull-requests: read" in job
    assert "contents: write" not in text
    assert "actions: write" not in text
    assert "security-events: write" not in text


def test_lifecycle_reconciliation_never_executes_pull_request_repository_code() -> None:
    text = _workflow_text()

    for blocked in (
        "actions/checkout@",
        "actions/setup-python@",
        "PYTHONPATH=src",
        "python -m sdetkit",
        "pip install",
        "git fetch",
        "git checkout",
        "bash quality.sh",
    ):
        assert blocked not in text
    assert "repository_code_execution_allowed=false" in text


def test_lifecycle_reconciliation_updates_only_existing_bot_quality_comment() -> None:
    text = _workflow_text()

    assert 'row["user"].get("type") == "Bot"' in text
    assert 'str(row.get("body") or "").startswith("### SDET Quality Gate")' in text
    assert "repos/{repository}/issues/comments/{comment_id}" in text
    assert 'method="PATCH"' in text
    assert "missing_comment" in text
    assert "comment_creation_allowed=false" in text
    assert 'method="POST"' not in text
    assert "issues.createComment" not in text


def test_lifecycle_reconciliation_requires_github_merged_state_and_exact_identity() -> None:
    text = _workflow_text()

    assert 'merged = bool(pull.get("merged_at"))' in text
    assert 'state = str(pull.get("state") or "")' in text
    assert 'merge_commit_sha = str(pull.get("merge_commit_sha") or "")' in text
    assert 'head_sha = str(head.get("sha") or "")' in text
    assert 'merged and state == "closed" and merge_commit_sha and head_sha' in text
    assert "Final PR head" in text
    assert "Merge commit" in text


def test_lifecycle_reconciliation_supersedes_stale_verdict_without_claiming_proof() -> None:
    text = _workflow_text()

    assert '"## ✅ Merged"' in text
    assert "earlier pre-merge Quality Gate snapshot is historical" in text
    assert "Previous Quality Gate report" in text
    assert "Superseded after merge" in text
    assert "does not authorize the merge or retroactively prove individual checks" in text
    assert '"reporting_only": True' in text
    assert '"merge_authorized": False' in text
    assert '"semantic_equivalence_proven": False' in text


def test_lifecycle_reconciliation_is_idempotent_and_emits_audit_artifact() -> None:
    text = _workflow_text()

    assert 'if "## ✅ Merged" in existing_body:' in text
    assert "already_reconciled" in text
    assert "build/pr-quality-lifecycle/reconciliation.json" in text
    assert "Upload lifecycle reconciliation evidence" in text
    assert "name: pr-quality-lifecycle-reconciliation" in text
    assert "retention-days: 14" in text
