from __future__ import annotations

import json
from pathlib import Path

from sdetkit.release_anti_hijack_threat_model import build_release_anti_hijack_threat_model


def test_release_provenance_permission_evidence_matches_governance_summary() -> None:
    report = json.loads(
        Path("build/sdetkit/workflow-governance-report.json").read_text(encoding="utf-8")
    )
    evidence = json.loads(
        Path("build/sdetkit/workflow-permission-release-provenance-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    groups = {group["kind"]: group for group in report["permission_review_summary"]["groups"]}
    target_group = groups["release_or_provenance"]

    assert evidence["schema_version"] == 1
    assert evidence["report_status"] == "review_required"
    assert evidence["evidence_type"] == "permission_group_evidence"
    assert evidence["permission_group"] == "release_or_provenance"
    assert evidence["workflow_count"] == target_group["workflow_count"] == 1
    assert evidence["workflows"] == target_group["workflows"]
    assert evidence["granted_write_scopes"] == target_group["granted_write_scopes"]
    assert evidence["requires_human_review"] is True
    assert evidence["safe_to_patch"] is False
    assert evidence["review_first"] is True
    assert evidence["workflow_mutation"] is False
    assert evidence["automatic_permission_reduction_allowed"] is False
    assert evidence["next_allowed_action"] == "collect_human_review_evidence"


def test_release_provenance_permission_evidence_uses_release_threat_model() -> None:
    threat_model = build_release_anti_hijack_threat_model()
    evidence = json.loads(
        Path("build/sdetkit/workflow-permission-release-provenance-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    assert evidence["workflows"] == [".github/workflows/release.yml"]
    assert evidence["release_threat_model"]["status"] == threat_model["status"]
    assert evidence["release_threat_model"]["workflow_path"] == ".github/workflows/release.yml"
    assert evidence["release_threat_model"]["finding_count"] == threat_model.get(
        "finding_count",
        len(threat_model.get("findings", [])),
    )
    assert evidence["release_threat_model"]["workflow_mutation"] is False
    assert evidence["release_threat_model"]["review_first"] is True


def test_release_provenance_permission_evidence_keeps_other_groups_separate() -> None:
    evidence = json.loads(
        Path("build/sdetkit/workflow-permission-release-provenance-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    assert ".github/workflows/pages.yml" not in evidence["workflows"]
    assert ".github/workflows/security.yml" not in evidence["workflows"]
    assert ".github/workflows/dependency-auto-merge.yml" not in evidence["workflows"]

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
