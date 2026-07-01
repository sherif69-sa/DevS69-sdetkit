from __future__ import annotations

import json
from pathlib import Path

EVIDENCE = Path(".github/workflows/pr-quality-comment.yml")
PUBLISHER = Path(".github/workflows/pr-quality-publisher.yml")
TOPOLOGY = Path("docs/contracts/workflow-topology.v1.json")
DECISION = Path("docs/ci/workflow-permission-decisions/pr-quality-trusted-publisher.md")


def _snake(*parts: str) -> str:
    return "_".join(parts)


def _kv(key: str, value: str) -> str:
    return f"{key}={value}"


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


def test_topology_keeps_pr_quality_workflows_in_reviewed_inventory() -> None:
    payload = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    inventory = set(payload["inventory"])

    assert ".github/workflows/pr-quality-comment.yml" in inventory
    assert ".github/workflows/pr-quality-publisher.yml" in inventory
    assert payload["budgets"]["maximum_workflow_count"] >= len(inventory)
    assert payload["reviewed_growth"]["current_workflow_count"] == len(inventory)
    assert payload["reviewed_growth"]["reviewer"] == "sherif69-sa"


def test_scoped_permission_decision_is_explicit() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert _kv("decision", _snake("approved", "scoped", "permission", "move")) in text
    assert _kv("reviewer", "sherif69-sa") in text
    assert _kv(_snake("publisher", "trigger"), _snake("workflow", "run")) in text
    assert _kv(_snake("publisher", "checkout", "allowed"), "false") in text
    assert (
        _kv(
            _snake("publisher", "repository", "code", "execution", "allowed"),
            "false",
        )
        in text
    )
    assert _kv(_snake("merge", "authorized"), "false") in text
    assert _kv(_snake("remaining", "group", "workflows", "pending"), "true") in text


def test_publisher_visibility_stays_inside_verified_handoff_boundary() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    visibility = publisher[
        publisher.index(
            "- name: Verify PR Quality comment visibility"
        ) : publisher.index("- name: Upload PR quality publication artifacts")
    ]

    snapshot_exit_path = (
        "build/pr-quality/trusted-diagnostic-signal-snapshot-history/exit-code.txt"
    )

    assert snapshot_exit_path in evidence
    assert snapshot_exit_path not in visibility
    assert 'snapshot_history_validation_key = "_".join(' in visibility
    assert (
        '("trusted", "diagnostic", "signal", "snapshot", "history", "validation")'
        in visibility
    )
    assert 'snapshot_history_validation_value = "_".join(' in visibility
    assert '("represented", "by", "verified", "handoff", "metadata")' in visibility
    assert 'if trusted_history_collection_status != "collected":' in visibility
    assert 'if trusted_history_status != "trusted_history_verified":' in visibility
    assert "publisher handoff digest mismatch" in publisher
