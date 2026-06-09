from __future__ import annotations

import json
from pathlib import Path


def test_repository_mutation_permission_evidence_matches_governance_summary() -> None:
    report = json.loads(
        Path("build/sdetkit/workflow-governance-report.json").read_text(encoding="utf-8")
    )
    evidence = json.loads(
        Path("build/sdetkit/workflow-permission-repository-mutation-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    groups = {group["kind"]: group for group in report["permission_review_summary"]["groups"]}
    repo_group = groups["repository_mutation"]

    assert evidence["schema_version"] == 1
    assert evidence["report_status"] == "review_required"
    assert evidence["evidence_type"] == ("workflow_permission_repository_mutation_evidence")
    assert evidence["permission_group"] == "repository_mutation"
    assert evidence["workflow_count"] == repo_group["workflow_count"] == 5
    assert evidence["workflows"] == repo_group["workflows"]
    assert evidence["granted_write_scopes"] == repo_group["granted_write_scopes"]
    assert evidence["requires_human_review"] is True
    assert evidence["safe_to_patch"] is False
    assert evidence["review_first"] is True
    assert evidence["workflow_mutation"] is False
    assert evidence["automatic_permission_reduction_allowed"] is False
    assert evidence["next_allowed_action"] == "collect_human_review_evidence"


def test_repository_mutation_permission_evidence_keeps_release_separate() -> None:
    evidence = json.loads(
        Path("build/sdetkit/workflow-permission-repository-mutation-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    assert ".github/workflows/release.yml" not in evidence["workflows"]
    assert evidence["workflows"] == [
        ".github/workflows/dependency-auto-merge.yml",
        ".github/workflows/maintenance-issue-command-center.yml",
        ".github/workflows/maintenance-on-demand.yml",
        ".github/workflows/pre-commit-autoupdate.yml",
        ".github/workflows/weekly-maintenance.yml",
    ]

    assert evidence["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    assert evidence["automation_allowed"] is False
    assert evidence["patch_application_allowed"] is False
    assert evidence["merge_authorized"] is False
    assert evidence["semantic_equivalence_proven"] is False
