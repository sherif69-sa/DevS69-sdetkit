from __future__ import annotations

import copy
from pathlib import Path

import pytest

from sdetkit import workflow_permission_review_worklist as worklist


def _packet(
    *,
    review_id: str = "review-example",
    workflow: str = ".github/workflows/example.yml",
    permission_group: str = "repository_mutation",
    packet_digest: str = "packet-marker",
) -> dict[str, object]:
    return {
        "packet_id": f"packet-{review_id}",
        "review_id": review_id,
        "workflow": workflow,
        "workflow_sha256": "workflow-marker",
        "permission_group": permission_group,
        "packet_digest": packet_digest,
        "safe_to_patch": False,
        "current_permissions": {
            "write_scopes": ["contents: write", "issues: write"],
        },
        "triage_signals": {
            "write_scope_count": 2,
            "contains_contents_write": True,
            "multiple_write_scopes": True,
            "classification_is_decision": False,
        },
        "evidence": {
            "required_human_evidence": ["confirm the exact write-scope need"],
            "retained_evidence_refs": ["docs/ci/workflow-permission-review-cards/example.md"],
        },
        "decision_boundary": {
            "allowed_decisions": ["keep", "reduce", "split", "defer"],
        },
        "authority_boundary": {"workflow_mutation_allowed": False},
    }


def _lifecycle(
    *,
    review_id: str = "review-example",
    workflow: str = ".github/workflows/example.yml",
    permission_group: str = "repository_mutation",
    state: str = "pending_human_review",
    action: str = "complete_human_permission_review",
    packet_digest: str = "packet-marker",
    human_decision: str | None = None,
    decision_record_ref: str | None = None,
    plan_id: str | None = None,
    plan_digest: str | None = None,
    integrity_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "review_id": review_id,
        "workflow": workflow,
        "workflow_sha256": "workflow-marker",
        "permission_group": permission_group,
        "lifecycle_state": state,
        "next_human_action": action,
        "packet_digest": packet_digest,
        "human_decision": human_decision,
        "decision_record_ref": decision_record_ref,
        "plan_id": plan_id,
        "plan_digest": plan_digest,
        "integrity_reasons": integrity_reasons or [],
    }


def _state(
    items: list[dict[str, object]], *, status: str = "human_action_required"
) -> dict[str, object]:
    return {
        "status": status,
        "bundle_digest": "state-bundle-marker",
        "input_provenance": {"input_digest": "state-input-marker"},
        "integrity": {"global_reasons": []},
        "lifecycle": items,
    }


def _packet_index(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "bundle_digest": "packet-bundle-marker",
        "input_provenance": {"input_digest": "packet-input-marker"},
        "packets": items,
    }


def _install_inputs(
    monkeypatch: pytest.MonkeyPatch,
    state: dict[str, object],
    packets: dict[str, object],
) -> None:
    monkeypatch.setattr(
        worklist,
        "build_workflow_permission_governance_state_machine",
        lambda _root: state,
    )
    monkeypatch.setattr(
        worklist,
        "build_workflow_permission_review_packet_index",
        lambda _root: packets,
    )


def test_pending_review_becomes_exact_packet_bound_human_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lifecycle = _lifecycle()
    packet = _packet()
    _install_inputs(monkeypatch, _state([lifecycle]), _packet_index([packet]))

    payload = worklist.build_workflow_permission_review_worklist(tmp_path)
    item = payload["work_items"][0]

    assert payload["status"] == "human_work_required"
    assert payload["summary"]["work_item_count"] == 1
    assert payload["summary"]["review_action_count"] == 1
    assert item["next_human_action"] == "complete_human_permission_review"
    assert item["packet_digest"] == "packet-marker"
    assert item["current_write_scopes"] == ["contents: write", "issues: write"]
    assert item["allowed_human_decisions"] == ["keep", "reduce", "split", "defer"]
    assert item["required_human_evidence"] == ["confirm the exact write-scope need"]
    assert item["machine_recommendation"] is None
    assert item["review_priority"] is None
    assert item["reviewer_assignment"] is None
    assert item["decision_prefill"] is None
    assert item["safe_to_patch"] is False
    assert not any(item["authority_boundary"].values())
    assert payload["action_lanes"][0]["next_human_action"] == "complete_human_permission_review"


def test_resolved_keep_is_not_active_work(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lifecycle = _lifecycle(
        state="resolved_keep",
        action="none",
        human_decision="keep",
        decision_record_ref="docs/ci/workflow-permission-decisions/example.json",
    )
    _install_inputs(monkeypatch, _state([lifecycle], status="complete"), _packet_index([_packet()]))

    payload = worklist.build_workflow_permission_review_worklist(tmp_path)

    assert payload["status"] == "not_required"
    assert payload["summary"]["work_item_count"] == 0
    assert payload["summary"]["resolved_no_action_count"] == 1
    assert payload["work_items"] == []


def test_deferred_review_retains_human_revisit_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lifecycle = _lifecycle(
        state="deferred",
        action="revisit_deferred_permission_review",
        human_decision="defer",
        decision_record_ref="docs/ci/workflow-permission-decisions/example.json",
    )
    _install_inputs(monkeypatch, _state([lifecycle]), _packet_index([_packet()]))

    payload = worklist.build_workflow_permission_review_worklist(tmp_path)
    item = payload["work_items"][0]

    assert item["next_human_action"] == "revisit_deferred_permission_review"
    assert item["current_human_decision"] == "defer"
    assert item["allowed_human_decisions"] == ["keep", "reduce", "split", "defer"]
    assert payload["summary"]["review_action_count"] == 1


def test_implementation_item_exposes_plan_binding_without_decision_prefill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lifecycle = _lifecycle(
        state="implementation_plan_required",
        action="complete_permission_change_plan",
        human_decision="split",
        decision_record_ref="docs/ci/workflow-permission-decisions/example.json",
        plan_id="plan-example",
        plan_digest="plan-marker",
    )
    _install_inputs(monkeypatch, _state([lifecycle]), _packet_index([_packet()]))

    payload = worklist.build_workflow_permission_review_worklist(tmp_path)
    item = payload["work_items"][0]

    assert item["next_human_action"] == "complete_permission_change_plan"
    assert item["plan_id"] == "plan-example"
    assert item["plan_digest"] == "plan-marker"
    assert item["current_human_decision"] == "split"
    assert item["allowed_human_decisions"] == []
    assert item["decision_prefill"] is None
    assert item["safe_to_patch"] is False
    assert payload["summary"]["implementation_action_count"] == 1


def test_blocked_item_is_repair_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lifecycle = _lifecycle(
        state="blocked",
        action="repair_governance_evidence_binding",
        integrity_reasons=["packet_missing"],
    )
    _install_inputs(monkeypatch, _state([lifecycle], status="blocked"), _packet_index([]))

    payload = worklist.build_workflow_permission_review_worklist(tmp_path)
    item = payload["work_items"][0]

    assert payload["status"] == "blocked"
    assert payload["summary"]["blocked_repair_count"] == 1
    assert item["next_human_action"] == "repair_governance_evidence_binding"
    assert "packet_missing" in item["integrity_reasons"]
    assert item["allowed_human_decisions"] == []


def test_packet_binding_mismatch_cannot_enter_decision_lane(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lifecycle = _lifecycle()
    packet = _packet(packet_digest="different-packet-marker")
    _install_inputs(monkeypatch, _state([lifecycle]), _packet_index([packet]))

    payload = worklist.build_workflow_permission_review_worklist(tmp_path)
    item = payload["work_items"][0]

    assert payload["status"] == "blocked"
    assert item["next_human_action"] == "repair_governance_evidence_binding"
    assert "packet_digest_mismatch" in item["integrity_reasons"]
    assert item["allowed_human_decisions"] == []


def test_worklist_is_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    items = [
        _lifecycle(review_id="review-b", workflow=".github/workflows/b.yml"),
        _lifecycle(review_id="review-a", workflow=".github/workflows/a.yml"),
    ]
    packets = [
        _packet(review_id="review-b", workflow=".github/workflows/b.yml"),
        _packet(review_id="review-a", workflow=".github/workflows/a.yml"),
    ]
    _install_inputs(monkeypatch, _state(items), _packet_index(packets))

    first = worklist.build_workflow_permission_review_worklist(tmp_path)
    second = worklist.build_workflow_permission_review_worklist(tmp_path)

    assert first == second
    assert [item["workflow"] for item in first["work_items"]] == [
        ".github/workflows/a.yml",
        ".github/workflows/b.yml",
    ]
    assert first["bundle_digest"] == second["bundle_digest"]


def test_retained_worklist_validation_rejects_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(monkeypatch, _state([_lifecycle()]), _packet_index([_packet()]))
    payload = worklist.build_workflow_permission_review_worklist(tmp_path)
    tampered = copy.deepcopy(payload)
    tampered["bundle_digest"] = "tampered"

    validation = worklist.validate_workflow_permission_review_worklist(tmp_path, tampered)

    assert validation["status"] == "stale"
    assert validation["fresh"] is False
    assert validation["reasons"] == ["bundle_digest_mismatch"]
    assert not any(validation["authority_boundary"].values())


def test_repository_output_guard_and_external_export(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    assert (
        worklist._safe_output_path(root, Path("build/worklist.json"))
        == (root / "build" / "worklist.json").resolve()
    )
    with pytest.raises(ValueError, match="may only be written under build"):
        worklist._safe_output_path(root, Path("docs/ci/worklist.json"))

    external = tmp_path / "export" / "worklist.json"
    assert worklist._safe_output_path(root, external) == external.resolve()


def test_live_repository_worklist_never_infers_human_authority() -> None:
    payload = worklist.build_workflow_permission_review_worklist(".")

    assert payload["summary"]["machine_recommendation_count"] == 0
    assert payload["summary"]["machine_priority_count"] == 0
    assert payload["summary"]["automatic_reviewer_assignment_count"] == 0
    assert payload["summary"]["automatic_decision_count"] == 0
    assert payload["summary"]["automatic_permission_change_count"] == 0
    assert not any(payload["authority_boundary"].values())
    for item in payload["work_items"]:
        assert item["machine_recommendation"] is None
        assert item["review_priority"] is None
        assert item["reviewer_assignment"] is None
        assert item["decision_prefill"] is None
        assert item["safe_to_patch"] is False
        assert not any(item["authority_boundary"].values())
