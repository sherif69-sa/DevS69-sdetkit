from __future__ import annotations

import json
from pathlib import Path


def test_workflow_permission_evidence_index_covers_all_groups() -> None:
    index = json.loads(
        Path("build/sdetkit/workflow-permission-evidence-index.json").read_text(encoding="utf-8")
    )

    groups = {group["permission_group"]: group for group in index["groups"]}

    assert index["schema_version"] == 1
    assert index["report_status"] == "review_required"
    assert index["evidence_type"] == "workflow_permission_evidence_index"
    assert index["group_count"] == 5
    assert index["workflow_count"] == 16
    assert set(groups) == {
        "repository_mutation",
        "security_upload",
        "pr_issue_interaction",
        "deployment_or_oidc",
        "release_or_provenance",
    }


def test_workflow_permission_evidence_index_preserves_no_mutation_boundary() -> None:
    index = json.loads(
        Path("build/sdetkit/workflow-permission-evidence-index.json").read_text(encoding="utf-8")
    )

    assert index["review_first"] is True
    assert index["workflow_mutation"] is False
    assert index["automatic_permission_reduction_allowed"] is False
    assert index["next_allowed_action"] == "human_review_permission_evidence"
    assert index["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    for group in index["groups"]:
        assert group["requires_human_review"] is True
        assert group["safe_to_patch"] is False
        assert group["workflow_mutation"] is False
        assert Path(group["source_path"]).exists()
