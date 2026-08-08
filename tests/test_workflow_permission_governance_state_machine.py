from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import workflow_permission_governance_state_machine as state_machine

WORKFLOW = ".github/workflows/example.yml"
REVIEW_ID = "permission-review-example"
WORKFLOW_DIGEST = "workflow-digest-fixture"
PACKET_DIGEST = "packet-digest-fixture"
PLAN_DIGEST = "plan-digest-fixture"
DECISION_REF = "docs/ci/workflow-permission-decisions/example.decision.json"


def _zero_authority() -> dict[str, bool]:
    return state_machine.authority_boundary()


def _control(*, decision: str | None = None) -> dict[str, object]:
    recorded = decision is not None
    return {
        "input_provenance": {"input_digest": "control-input-fixture"},
        "review_queue": [
            {
                "review_id": REVIEW_ID,
                "workflow": WORKFLOW,
                "workflow_sha256": WORKFLOW_DIGEST,
                "permission_group": "repository_mutation",
                "human_decision_recorded": recorded,
                "human_decision": decision,
                "decision_record_ref": DECISION_REF if recorded else None,
                "safe_to_patch": False,
                "authority_boundary": _zero_authority(),
            }
        ],
        "authority_boundary": _zero_authority(),
    }


def _packet(*, decision: str | None = None) -> dict[str, object]:
    recorded = decision is not None
    return {
        "input_provenance": {"input_digest": "packet-input-fixture"},
        "bundle_digest": "packet-bundle-fixture",
        "packets": [
            {
                "review_id": REVIEW_ID,
                "workflow": WORKFLOW,
                "workflow_sha256": WORKFLOW_DIGEST,
                "permission_group": "repository_mutation",
                "packet_digest": PACKET_DIGEST,
                "decision_boundary": {
                    "human_decision_recorded": recorded,
                    "current_human_decision": decision,
                    "decision_record_ref": DECISION_REF if recorded else None,
                },
                "safe_to_patch": False,
                "authority_boundary": _zero_authority(),
            }
        ],
        "authority_boundary": _zero_authority(),
    }


def _change(*, decision: str | None = None) -> dict[str, object]:
    plans: list[dict[str, object]] = []
    if decision in state_machine.PLAN_DECISIONS:
        plans.append(
            {
                "plan_id": "wpcp-example",
                "review_id": REVIEW_ID,
                "workflow": WORKFLOW,
                "workflow_sha256": WORKFLOW_DIGEST,
                "permission_group": "repository_mutation",
                "decision_binding": {
                    "decision": decision,
                    "decision_record_ref": DECISION_REF,
                },
                "plan_digest": PLAN_DIGEST,
                "ready_for_patch": False,
                "safe_to_patch": False,
                "authority_boundary": _zero_authority(),
            }
        )
    return {
        "input_provenance": {"input_digest": "change-input-fixture"},
        "bundle_digest": "change-bundle-fixture",
        "plans": plans,
        "missing_decision_record_bindings": [],
        "authority_boundary": _zero_authority(),
    }


def _wire(monkeypatch: pytest.MonkeyPatch, *, decision: str | None = None) -> None:
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_control_plane",
        lambda _root: _control(decision=decision),
    )
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_packet_index",
        lambda _root: _packet(decision=decision),
    )
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_change_plan_index",
        lambda _root: _change(decision=decision),
    )


def test_pending_review_has_exact_human_next_action(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch)

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)
    item = payload["lifecycle"][0]

    assert payload["status"] == "human_action_required"
    assert item["lifecycle_state"] == "pending_human_review"
    assert item["next_human_action"] == "complete_human_permission_review"
    assert item["safe_to_patch"] is False
    assert set(item["authority_boundary"].values()) == {False}


@pytest.mark.parametrize(
    ("decision", "lifecycle_state", "action"),
    [
        ("keep", "resolved_keep", "none"),
        ("defer", "deferred", "revisit_deferred_permission_review"),
    ],
)
def test_non_change_decisions_never_create_change_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    decision: str,
    lifecycle_state: str,
    action: str,
) -> None:
    _wire(monkeypatch, decision=decision)

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)
    item = payload["lifecycle"][0]

    assert item["lifecycle_state"] == lifecycle_state
    assert item["next_human_action"] == action
    assert item["plan_id"] is None


@pytest.mark.parametrize("decision", ["reduce", "split"])
def test_change_decision_requires_exact_non_executable_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    decision: str,
) -> None:
    _wire(monkeypatch, decision=decision)

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)
    item = payload["lifecycle"][0]

    assert payload["status"] == "human_action_required"
    assert item["lifecycle_state"] == "implementation_plan_required"
    assert item["next_human_action"] == "complete_permission_change_plan"
    assert item["plan_id"] == "wpcp-example"
    assert item["safe_to_patch"] is False


def test_missing_packet_blocks_instead_of_guessing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch)
    packets = _packet()
    packets["packets"] = []
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_packet_index",
        lambda _root: packets,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)
    item = payload["lifecycle"][0]

    assert payload["status"] == "blocked"
    assert item["next_human_action"] == "repair_governance_evidence_binding"
    assert "packet_missing" in item["integrity_reasons"]


def test_pending_review_with_plan_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch)
    changes = _change(decision="reduce")
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_change_plan_index",
        lambda _root: changes,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)

    assert payload["status"] == "blocked"
    assert "change_plan_without_human_decision" in payload["lifecycle"][0]["integrity_reasons"]


def test_reduce_without_plan_is_blocked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wire(monkeypatch, decision="reduce")
    changes = _change()
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_change_plan_index",
        lambda _root: changes,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)

    assert payload["status"] == "blocked"
    assert "change_plan_missing" in payload["lifecycle"][0]["integrity_reasons"]


def test_orphan_packet_and_plan_are_global_blockers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch)
    packets = _packet()
    packet_list = packets["packets"]
    assert isinstance(packet_list, list)
    orphan_packet = dict(packet_list[0])
    orphan_packet["review_id"] = "orphan-review"
    orphan_packet["workflow"] = ".github/workflows/orphan.yml"
    packets["packets"] = [*packet_list, orphan_packet]

    changes = _change(decision="reduce")
    plan_list = changes["plans"]
    assert isinstance(plan_list, list)
    orphan_plan = dict(plan_list[0])
    orphan_plan["review_id"] = "orphan-plan"
    orphan_plan["workflow"] = ".github/workflows/orphan-plan.yml"
    changes["plans"] = [orphan_plan]

    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_packet_index",
        lambda _root: packets,
    )
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_change_plan_index",
        lambda _root: changes,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)

    assert payload["status"] == "blocked"
    assert payload["summary"]["orphan_packet_count"] == 1
    assert payload["summary"]["orphan_change_plan_count"] == 1
    assert "orphan_packets" in payload["integrity"]["global_reasons"]
    assert "orphan_change_plans" in payload["integrity"]["global_reasons"]


def test_plan_binding_mismatch_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wire(monkeypatch, decision="split")
    changes = _change(decision="split")
    plan_list = changes["plans"]
    assert isinstance(plan_list, list)
    assert isinstance(plan_list[0], dict)
    plan_list[0]["workflow_sha256"] = "different-workflow-digest"
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_change_plan_index",
        lambda _root: changes,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)

    assert payload["status"] == "blocked"
    assert "plan_binding_mismatch:workflow_sha256" in payload["lifecycle"][0]["integrity_reasons"]


def test_upstream_authority_escalation_blocks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch)
    packets = _packet()
    packets["authority_boundary"] = {"workflow_mutation_allowed": True}
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_packet_index",
        lambda _root: packets,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)

    assert payload["status"] == "blocked"
    assert "review_packet_authority_boundary_invalid" in payload["integrity"]["global_reasons"]
    assert set(payload["authority_boundary"].values()) == {False}


def test_output_is_deterministic_and_tamper_becomes_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire(monkeypatch)

    first = state_machine.build_workflow_permission_governance_state_machine(tmp_path)
    second = state_machine.build_workflow_permission_governance_state_machine(tmp_path)
    assert first == second

    tampered = json.loads(json.dumps(first))
    tampered["lifecycle"][0]["next_human_action"] = "none"
    result = state_machine.validate_workflow_permission_governance_state_machine(tmp_path, tampered)

    assert result["fresh"] is False
    assert result["status"] == "stale"
    assert "lifecycle_mismatch" in result["reasons"]


def test_repository_local_output_is_build_only(tmp_path: Path) -> None:
    target = state_machine._safe_output_path(tmp_path, Path("build/sdetkit/state.json"))
    assert target == (tmp_path / "build" / "sdetkit" / "state.json").resolve()

    with pytest.raises(ValueError, match="only be written under build"):
        state_machine._safe_output_path(tmp_path, Path("docs/ci/state.json"))


def test_cli_writes_json_without_granting_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _wire(monkeypatch)

    result = state_machine.main(
        [
            "--root",
            str(tmp_path),
            "--out",
            "build/sdetkit/state.json",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    retained = json.loads(
        (tmp_path / "build" / "sdetkit" / "state.json").read_text(encoding="utf-8")
    )
    assert result == 0
    assert retained == payload
    assert payload["status"] == "human_action_required"
    assert set(payload["authority_boundary"].values()) == {False}


def test_empty_governance_queue_is_not_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    control = _control()
    control["review_queue"] = []
    packets = _packet()
    packets["packets"] = []
    changes = _change()
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_control_plane",
        lambda _root: control,
    )
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_review_packet_index",
        lambda _root: packets,
    )
    monkeypatch.setattr(
        state_machine,
        "build_workflow_permission_change_plan_index",
        lambda _root: changes,
    )

    payload = state_machine.build_workflow_permission_governance_state_machine(tmp_path)

    assert payload["status"] == "not_required"
    assert payload["summary"]["workflow_count"] == 0
    assert payload["lifecycle"] == []
