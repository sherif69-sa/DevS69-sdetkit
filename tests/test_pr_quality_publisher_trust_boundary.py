from __future__ import annotations

import json
from pathlib import Path

EVIDENCE = Path(".github/workflows/pr-quality-comment.yml")
PUBLISHER = Path(".github/workflows/pr-quality-publisher.yml")
TOPOLOGY = Path("docs/contracts/workflow-topology.v1.json")
DECISION = Path("docs/ci/workflow-permission-decisions/pr-quality-trusted-publisher.md")


def test_evidence_workflow_is_read_only_and_does_not_publish() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    permissions = text.split("jobs:", 1)[0]
    assert "issues: write" not in permissions
    assert "pull-requests: write" not in permissions
    assert "pull-requests: read" in permissions
    assert "- name: Comment on PR" not in text
    assert "- name: Verify PR Quality comment visibility" not in text
    assert "--method POST" not in text
    assert "--method PATCH" not in text


def test_publisher_is_default_branch_workflow_run_only() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    assert "name: PR Quality Publisher" in text
    assert "workflow_run:" in text
    assert 'workflows: ["PR Quality Comment"]' in text
    assert "pull_request:" not in text
    assert "pull_request_target:" not in text
    assert "github.event.workflow_run.conclusion == 'success'" in text


def test_publisher_has_narrow_write_permissions_and_no_repo_execution() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    assert "permissions: {}" in text.split("jobs:", 1)[0]
    assert "actions: read" in text
    assert "contents: read" in text
    assert "issues: write" in text
    assert "pull-requests: write" in text
    for blocked in (
        "actions/checkout@",
        "actions/setup-python@",
        "PYTHONPATH=src",
        "python -m sdetkit",
        "bash quality.sh",
        "git fetch",
        "git diff",
        "pip install",
    ):
        assert blocked not in text


def test_publisher_verifies_artifact_and_current_exact_head() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    assert "sdetkit.pr_quality_publisher_handoff.v1" in text
    assert "publisher handoff file allowlist mismatch" in text
    assert "publisher handoff contains a symlink" in text
    assert "publisher handoff digest mismatch" in text
    assert "publisher handoff binding mismatch" in text
    assert "publisher refuses stale evidence" in text
    assert "publisher refuses a non-open PR" in text
    assert "current-pr.json" in text
    assert "hashlib.sha256" in text


def test_publisher_neutralizes_active_content_and_mentions() -> None:
    text = PUBLISHER.read_text(encoding="utf-8")
    assert "PR Quality comment body exceeds publisher limit" in text
    assert "blocked active HTML" in text
    assert "blocked javascript URL" in text
    assert r"@\u200b" in text
    assert "Evidence is advisory and does not authorize merge." in text


def test_handoff_is_minimal_and_authority_non_authorizing() -> None:
    evidence = EVIDENCE.read_text(encoding="utf-8")
    assert "publisher_handoff_file_count" in evidence
    assert '"reporting_only": True' in evidence
    assert '"patch_application_allowed": False' in evidence
    assert '"security_dismissal_allowed": False' in evidence
    assert '"merge_authorized": False' in evidence
    assert '"semantic_equivalence_proven": False' in evidence


def test_topology_records_reviewed_security_growth() -> None:
    payload = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    assert payload["budgets"]["maximum_workflow_count"] == 56
    assert payload["reviewed_growth"]["previous_workflow_count"] == 55
    assert payload["reviewed_growth"]["current_workflow_count"] == 56
    assert "trusted workflow_run publisher" in payload["reviewed_growth"]["reason"]
    assert payload["reviewed_growth"]["reviewer"] == "sherif69-sa"


def test_scoped_permission_decision_is_explicit() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "decision=approved_scoped_permission_move" in text
    assert "reviewer=sherif69-sa" in text
    assert "publisher_trigger=workflow_run" in text
    assert "publisher_checkout_allowed=false" in text
    assert "publisher_repository_code_execution_allowed=false" in text
    assert "merge_authorized=false" in text
    assert "remaining_group_workflows_pending=true" in text
