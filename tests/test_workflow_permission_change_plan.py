from __future__ import annotations

import copy
import json
from pathlib import Path

from sdetkit import workflow_permission_change_plan as change_plan


def _entry(
    root: Path,
    *,
    workflow: str = ".github/workflows/example.yml",
    decision: str = "reduce",
    record_name: str = "example.decision.json",
    create_record: bool = True,
) -> dict[str, object]:
    record_ref = f"docs/ci/workflow-permission-decisions/{record_name}"
    if create_record:
        path = root / record_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "sdetkit.workflow_permission_decision_record.v1",
                    "review_id": "wpr-example",
                    "workflow": workflow,
                    "decision": decision,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return {
        "review_id": "wpr-example",
        "workflow": workflow,
        "workflow_sha256": "a" * 64,
        "permission_group": "repository_mutation",
        "granted_write_scopes": ["contents: write", "issues: write"],
        "human_decision_recorded": True,
        "human_decision": decision,
        "decision_record_ref": record_ref,
        "proposed_change": {
            "kind": "permission_only",
            "summary": "Narrow or split the reviewed write scopes.",
            "evidence_ref": "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181",
        },
        "proof_contract": ["exact-head CI", "workflow-specific execution proof"],
        "rollback_contract": {
            "strategy": "restore_exact_workflow_bytes",
            "workflow_sha256": "a" * 64,
        },
    }


def _plane(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "input_provenance": {"input_digest": "control-plane-digest"},
        "review_queue": entries,
    }


def _install_plane(monkeypatch, plane: dict[str, object]) -> None:
    monkeypatch.setattr(
        change_plan,
        "build_workflow_permission_review_control_plane",
        lambda _root: plane,
    )


def _complete_candidate(template: dict[str, object]) -> dict[str, object]:
    candidate = copy.deepcopy(template)
    implementation = candidate["implementation"]
    assert isinstance(implementation, dict)
    implementation["top_level_permissions"] = {
        "contents": "read",
        "issues": "read",
    }
    implementation["job_permissions"] = {
        "publisher": {
            "contents": "write",
        }
    }
    implementation["implementation_rationale"] = (
        "Retain the reviewed contents write scope only on the job that needs it."
    )
    implementation["proof_execution_refs"] = []
    implementation["rollback_execution_ref"] = None
    return candidate


def test_live_repository_requires_no_change_plan_without_human_reduce_or_split() -> None:
    payload = change_plan.build_workflow_permission_change_plan_index(".")

    assert payload["status"] == "not_required"
    assert payload["summary"]["change_plan_count"] == 0
    assert payload["summary"]["reduce_or_split_decision_count"] == 0
    assert payload["summary"]["automatic_patch_generation_allowed"] is False
    assert payload["summary"]["automatic_permission_change_allowed"] is False
    assert payload["plans"] == []
    assert not any(payload["authority_boundary"].values())


def test_pending_review_never_creates_change_plan(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    entry["human_decision_recorded"] = False
    entry["human_decision"] = None
    _install_plane(monkeypatch, _plane([entry]))

    payload = change_plan.build_workflow_permission_change_plan_index(tmp_path)

    assert payload["status"] == "not_required"
    assert payload["summary"]["pending_human_review_count"] == 1
    assert payload["plans"] == []


def test_keep_and_defer_are_non_change_decisions(monkeypatch, tmp_path: Path) -> None:
    keep = _entry(
        tmp_path, workflow=".github/workflows/keep.yml", decision="keep", record_name="keep.json"
    )
    defer = _entry(
        tmp_path,
        workflow=".github/workflows/defer.yml",
        decision="defer",
        record_name="defer.json",
    )
    _install_plane(monkeypatch, _plane([keep, defer]))

    payload = change_plan.build_workflow_permission_change_plan_index(tmp_path)

    assert payload["status"] == "not_required"
    assert payload["summary"]["non_change_decision_count"] == 2
    assert payload["summary"]["change_plan_count"] == 0
    assert payload["plans"] == []


def test_reduce_decision_creates_blank_non_executable_plan(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path, decision="reduce")
    _install_plane(monkeypatch, _plane([entry]))

    payload = change_plan.build_workflow_permission_change_plan_index(tmp_path)
    plan = payload["plans"][0]
    implementation = plan["implementation"]

    assert payload["status"] == "human_implementation_plan_required"
    assert payload["summary"]["change_plan_count"] == 1
    assert plan["decision_binding"]["decision"] == "reduce"
    assert plan["decision_binding"]["decision_record_sha256"]
    assert plan["plan_digest"] == change_plan._plan_digest(plan)
    assert implementation["implementation_scope"] == "permissions_only"
    assert implementation["top_level_permissions"] is None
    assert implementation["job_permissions"] is None
    assert implementation["implementation_rationale"] is None
    assert implementation["human_completion_required"] is True
    assert plan["ready_for_patch"] is False
    assert plan["safe_to_patch"] is False
    assert plan["requires_separate_reviewed_pr"] is True
    assert not any(plan["authority_boundary"].values())


def test_split_decision_creates_same_review_first_plan_boundary(
    monkeypatch, tmp_path: Path
) -> None:
    entry = _entry(tmp_path, decision="split")
    _install_plane(monkeypatch, _plane([entry]))

    payload = change_plan.build_workflow_permission_change_plan_index(tmp_path)
    plan = payload["plans"][0]

    assert plan["decision_binding"]["decision"] == "split"
    assert plan["safe_to_patch"] is False
    assert not any(plan["authority_boundary"].values())


def test_missing_retained_decision_record_blocks_plan_generation(
    monkeypatch, tmp_path: Path
) -> None:
    entry = _entry(tmp_path, create_record=False)
    _install_plane(monkeypatch, _plane([entry]))

    payload = change_plan.build_workflow_permission_change_plan_index(tmp_path)

    assert payload["status"] == "blocked"
    assert payload["summary"]["change_plan_count"] == 0
    assert payload["summary"]["missing_decision_record_binding_count"] == 1
    assert payload["missing_decision_record_bindings"] == [entry["workflow"]]


def test_decision_record_bytes_are_bound_into_plan(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    first = change_plan.build_workflow_permission_change_plan_index(tmp_path)
    record_path = tmp_path / str(entry["decision_record_ref"])
    record_path.write_text(record_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    second = change_plan.build_workflow_permission_change_plan_index(tmp_path)

    first_plan = first["plans"][0]
    second_plan = second["plans"][0]
    assert (
        first_plan["decision_binding"]["decision_record_sha256"]
        != second_plan["decision_binding"]["decision_record_sha256"]
    )
    assert first_plan["plan_digest"] != second_plan["plan_digest"]
    assert first["bundle_digest"] != second["bundle_digest"]


def test_structurally_valid_plan_still_does_not_authorize_patch(
    monkeypatch, tmp_path: Path
) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    template = change_plan.build_workflow_permission_change_plan_index(tmp_path)["plans"][0]
    candidate = _complete_candidate(template)

    validation = change_plan.validate_workflow_permission_change_plan(tmp_path, candidate)

    assert validation["status"] == "structurally_ready_for_separate_pr"
    assert validation["valid_current"] is True
    assert validation["new_write_scopes"] == []
    assert validation["implementation_authorized"] is False
    assert validation["safe_to_patch"] is False
    assert not any(validation["authority_boundary"].values())


def test_new_write_scope_is_rejected(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    template = change_plan.build_workflow_permission_change_plan_index(tmp_path)["plans"][0]
    candidate = _complete_candidate(template)
    implementation = candidate["implementation"]
    assert isinstance(implementation, dict)
    jobs = implementation["job_permissions"]
    assert isinstance(jobs, dict)
    jobs["publisher"]["packages"] = "write"

    validation = change_plan.validate_workflow_permission_change_plan(tmp_path, candidate)

    assert validation["status"] == "invalid"
    assert "packages: write" in validation["new_write_scopes"]
    assert "new_write_scope_forbidden:packages: write" in validation["invalid_reasons"]


def test_permission_levels_are_strict(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    template = change_plan.build_workflow_permission_change_plan_index(tmp_path)["plans"][0]
    candidate = _complete_candidate(template)
    implementation = candidate["implementation"]
    assert isinstance(implementation, dict)
    top = implementation["top_level_permissions"]
    assert isinstance(top, dict)
    top["contents"] = "admin"

    validation = change_plan.validate_workflow_permission_change_plan(tmp_path, candidate)

    assert validation["status"] == "invalid"
    assert "permission_level_invalid:contents" in validation["invalid_reasons"]


def test_blank_generated_plan_is_not_structurally_ready(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    template = change_plan.build_workflow_permission_change_plan_index(tmp_path)["plans"][0]

    validation = change_plan.validate_workflow_permission_change_plan(tmp_path, template)

    assert validation["status"] == "invalid"
    assert "target_permissions_missing" in validation["invalid_reasons"]
    assert "implementation_rationale_missing" in validation["invalid_reasons"]


def test_binding_tampering_is_stale(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    template = change_plan.build_workflow_permission_change_plan_index(tmp_path)["plans"][0]
    candidate = _complete_candidate(template)
    candidate["workflow_sha256"] = "b" * 64

    validation = change_plan.validate_workflow_permission_change_plan(tmp_path, candidate)

    assert validation["status"] == "stale"
    assert "binding_mismatch:workflow_sha256" in validation["stale_reasons"]


def test_authority_escalation_is_invalid(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    template = change_plan.build_workflow_permission_change_plan_index(tmp_path)["plans"][0]
    candidate = _complete_candidate(template)
    candidate["authority_boundary"]["patch_application_allowed"] = True

    validation = change_plan.validate_workflow_permission_change_plan(tmp_path, candidate)

    assert validation["status"] == "invalid"
    assert "authority_boundary_mismatch" in validation["invalid_reasons"]


def test_retained_index_freshness_rejects_tampering(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))
    payload = change_plan.build_workflow_permission_change_plan_index(tmp_path)
    tampered = copy.deepcopy(payload)
    tampered["bundle_digest"] = "tampered"

    validation = change_plan.validate_workflow_permission_change_plan_index(tmp_path, tampered)

    assert validation["fresh"] is False
    assert validation["status"] == "stale"
    assert validation["reasons"] == ["bundle_digest_mismatch"]


def test_change_plan_generation_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    _install_plane(monkeypatch, _plane([entry]))

    first = change_plan.build_workflow_permission_change_plan_index(tmp_path)
    second = change_plan.build_workflow_permission_change_plan_index(tmp_path)

    assert first == second
    assert first["bundle_digest"] == second["bundle_digest"]
