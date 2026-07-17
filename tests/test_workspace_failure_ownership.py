from __future__ import annotations

import json
from pathlib import Path

from sdetkit.workspace_failure_ownership import (
    WorkspaceDefinition,
    build_workspace_failure_bundle,
    normalize_saved_workspace_failure,
    render_workspace_failure_bundle,
)

FIXTURE_ROOT = Path("tests/fixtures/ci_failures/mixed_monorepo")
WORKSPACES = (
    WorkspaceDefinition("apps/admin", "javascript_typescript", "apps/admin/package.json"),
    WorkspaceDefinition("apps/web", "javascript_typescript", "apps/web/package.json"),
    WorkspaceDefinition("crates/native", "rust", "crates/native/Cargo.toml"),
)
AUTHORITY_FIELDS = {
    "target_code_execution",
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "publication_authorized",
    "merge_authorized",
    "semantic_equivalence_proven",
}


def _logs(*relative: str) -> list[Path]:
    return [FIXTURE_ROOT / item for item in relative]


def _by_workspace(payload: dict) -> dict[str, dict]:
    return {str(item["workspace_identity"]["path"]): item for item in payload["workspace_failures"]}


def test_saved_failures_keep_workspace_and_evidence_identity() -> None:
    payload = build_workspace_failure_bundle(
        _logs("admin/shared_test.log", "web/shared_test.log", "native/shared_test.log"),
        workspaces=WORKSPACES,
        evidence_root=FIXTURE_ROOT,
    )

    assert payload["failure_vector_count"] == 3
    assert payload["summary"] == {
        "by_workspace": {"apps/admin": 1, "apps/web": 1, "crates/native": 1},
        "by_ecosystem": {"javascript_typescript": 2, "rust": 1},
        "high_confidence_ownership_count": 3,
        "low_confidence_ownership_count": 0,
        "review_first_count": 3,
    }

    by_workspace = _by_workspace(payload)
    admin = by_workspace["apps/admin"]
    web = by_workspace["apps/web"]
    native = by_workspace["crates/native"]

    assert admin["evidence_source"] == "admin/shared_test.log"
    assert web["evidence_source"] == "web/shared_test.log"
    assert native["evidence_source"] == "native/shared_test.log"
    assert admin["failure_vector"]["adapter"]["ecosystem"] == "javascript_typescript"
    assert native["failure_vector"]["adapter"]["ecosystem"] == "rust"

    assert admin["failure_vector"]["failing_test_or_check"] == "shared_test"
    assert web["failure_vector"]["failing_test_or_check"] == "shared_test"
    assert Path(admin["failure_vector"]["affected_files"][0]).name == "shared.test.ts"
    assert Path(web["failure_vector"]["affected_files"][0]).name == "shared.test.ts"
    assert admin["identity_key"] != web["identity_key"]

    for workspace, item in by_workspace.items():
        assert item["failure_vector"]["workspace_identity"]["path"] == workspace
        assert item["safety_gate"]["workspace_identity"]["path"] == workspace
        assert item["protected_verifier"]["workspace_identity"]["path"] == workspace
        assert item["safety_gate"]["review_first"] is True
        assert item["protected_verifier"]["decision"]["review_first"] is True
        assert item["protected_verifier"]["synthetic_patch_created"] is False
        assert item["review_first"] is True


def test_ambiguous_multi_workspace_log_fails_closed() -> None:
    path = FIXTURE_ROOT / "ambiguous/mixed_shared_test.log"
    result = normalize_saved_workspace_failure(
        path.read_text(encoding="utf-8"),
        workspaces=WORKSPACES,
        evidence_source="ambiguous/mixed_shared_test.log",
        check="shared_test",
    ).to_dict()

    assert result["workspace_identity"] == {
        "path": "unknown",
        "ecosystem": "unknown",
        "manifest": "unknown",
    }
    assert [item["path"] for item in result["candidate_workspaces"]] == [
        "apps/admin",
        "crates/native",
    ]
    assert result["ownership_confidence"] == "low"
    assert result["uncertainty"] == ["multiple_workspace_candidates:apps/admin,crates/native"]
    assert result["failure_vector"]["failure_class"] == "unknown"
    assert result["failure_vector"]["adapter"]["confidence"] == "low"
    assert result["failure_vector"]["local_repro_command"] is None
    assert result["safety_gate"]["review_first"] is True
    assert result["protected_verifier"]["decision"]["review_first"] is True
    assert result["synthetic_patch_created"] is False
    assert result["target_code_execution"] is False


def test_workspace_failure_bundle_is_deterministic() -> None:
    paths = _logs("admin/shared_test.log", "web/shared_test.log", "native/shared_test.log")
    first = build_workspace_failure_bundle(
        paths,
        workspaces=WORKSPACES,
        evidence_root=FIXTURE_ROOT,
    )
    second = build_workspace_failure_bundle(
        list(reversed(paths)),
        workspaces=tuple(reversed(WORKSPACES)),
        evidence_root=FIXTURE_ROOT,
    )

    assert render_workspace_failure_bundle(first) == render_workspace_failure_bundle(second)
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_workspace_failure_bundle_preserves_false_authority() -> None:
    payload = build_workspace_failure_bundle(
        _logs("admin/shared_test.log", "ambiguous/mixed_shared_test.log"),
        workspaces=WORKSPACES,
        evidence_root=FIXTURE_ROOT,
    )

    assert set(payload["authority_boundary"]) == AUTHORITY_FIELDS
    assert set(payload["authority_boundary"].values()) == {False}
    assert payload["target_code_execution"] is False
    assert payload["synthetic_patch_created"] is False
    for item in payload["workspace_failures"]:
        assert set(item["authority_boundary"]) == AUTHORITY_FIELDS
        assert set(item["authority_boundary"].values()) == {False}
