from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from sdetkit import workflow_permission_decision_record as decision_record
from sdetkit import workflow_permission_review_control_plane as control_plane
from sdetkit import workflow_permission_review_packet as review_packet


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _packet_by_workflow(payload: dict[str, object], workflow: str) -> dict[str, object]:
    packets = payload["packets"]
    assert isinstance(packets, list)
    for item in packets:
        if isinstance(item, dict) and item.get("workflow") == workflow:
            return item
    raise AssertionError(f"packet not found for {workflow}")


def test_live_packet_index_mirrors_control_plane_without_machine_decisions() -> None:
    plane = control_plane.build_workflow_permission_review_control_plane(".")
    payload = review_packet.build_workflow_permission_review_packet_index(".")

    assert payload["summary"]["packet_count"] == plane["summary"]["permission_review_count"]
    assert (
        payload["summary"]["pending_human_review_count"]
        == plane["summary"]["pending_human_review_count"]
    )
    assert (
        payload["summary"]["human_decision_recorded_count"]
        == plane["summary"]["human_decision_recorded_count"]
    )
    assert payload["summary"]["machine_recommendation_count"] == 0
    assert payload["summary"]["automatic_permission_change_allowed"] is False
    assert not any(payload["authority_boundary"].values())

    packet_workflows = {item["workflow"] for item in payload["packet_index"]}
    plane_workflows = {item["workflow"] for item in plane["review_queue"]}
    assert packet_workflows == plane_workflows


def test_every_live_packet_is_bound_to_exact_workflow_bytes() -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")

    for packet in payload["packets"]:
        workflow = Path(packet["workflow"])
        assert workflow.is_file()
        assert packet["workflow_sha256"] == _sha256(workflow)
        assert packet["packet_digest"] == review_packet._packet_digest(packet)
        assert packet["safe_to_patch"] is False
        assert not any(packet["authority_boundary"].values())


def test_pending_packet_template_never_prefills_human_decision() -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")

    pending_packets = [
        packet
        for packet in payload["packets"]
        if packet["decision_boundary"]["human_decision_recorded"] is False
    ]
    assert pending_packets
    for packet in pending_packets:
        boundary = packet["decision_boundary"]
        assert boundary["machine_recommendation"] is None
        assert boundary["generated_packet_may_choose_decision"] is False
        template = boundary["decision_record_template"]
        assert template["template_only"] is True
        assert template["human_completion_required"] is True
        assert template["decision"] is None
        assert template["reviewer"] is None
        assert template["reviewer_evidence"] is None
        assert template["decided_at"] is None
        assert template["rationale"] is None
        assert template["proposed_change"] is None
        assert not any(template["authority_boundary"].values())


def test_blank_packet_template_is_not_a_valid_human_decision_record() -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")
    packet = next(
        item
        for item in payload["packets"]
        if item["decision_boundary"]["human_decision_recorded"] is False
    )
    template = packet["decision_boundary"]["decision_record_template"]
    review_entry = {
        "review_id": packet["review_id"],
        "workflow": packet["workflow"],
        "workflow_sha256": packet["workflow_sha256"],
        "permission_group": packet["permission_group"],
    }

    validation = decision_record.validate_decision_record(template, review_entry)

    assert validation["valid_current"] is False
    assert validation["status"] == "invalid"
    assert "decision_invalid" in validation["reasons"]
    assert "reviewer_missing" in validation["reasons"]
    assert "reviewer_evidence_missing" in validation["reasons"]
    assert "rationale_missing" in validation["reasons"]


def test_existing_review_cards_are_retained_as_evidence_not_decisions() -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")

    pages = _packet_by_workflow(payload, ".github/workflows/pages.yml")
    pages_refs = pages["evidence"]["review_card_refs"]
    assert "docs/ci/workflow-permission-review-cards/deployment-oidc-pages.md" in pages_refs
    assert pages["decision_boundary"]["machine_recommendation"] is None

    contributor = _packet_by_workflow(
        payload,
        ".github/workflows/contributor-onboarding-bot.yml",
    )
    contributor_refs = contributor["evidence"]["review_card_refs"]
    assert "docs/ci/workflow-permission-review-cards/pr-issue-interaction.md" in contributor_refs
    assert contributor["evidence"]["generated_packet_is_human_evidence"] is False


def test_packet_generation_is_deterministic() -> None:
    first = review_packet.build_workflow_permission_review_packet_index(".")
    second = review_packet.build_workflow_permission_review_packet_index(".")

    assert first == second
    assert first["bundle_digest"] == second["bundle_digest"]


def test_bundle_writer_round_trips_through_freshness_validator(tmp_path: Path) -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")
    paths = review_packet.write_workflow_permission_review_packet_bundle(
        ".",
        tmp_path,
        index=payload,
    )
    index_path = tmp_path / review_packet.DEFAULT_INDEX_NAME
    retained = json.loads(index_path.read_text(encoding="utf-8"))

    validation = review_packet.validate_workflow_permission_review_packet_index(".", retained)

    assert validation["fresh"] is True
    assert validation["reasons"] == []
    assert paths["index_path"] == index_path.as_posix()
    assert (tmp_path / review_packet.DEFAULT_MARKDOWN_INDEX_NAME).is_file()
    for item in payload["packet_index"]:
        assert (tmp_path / item["json_path"]).is_file()
        assert (tmp_path / item["markdown_path"]).is_file()


def test_freshness_rejects_packet_or_bundle_tampering() -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")
    tampered = copy.deepcopy(payload)
    tampered["bundle_digest"] = "tampered"
    tampered["packets"][0]["safe_to_patch"] = True

    validation = review_packet.validate_workflow_permission_review_packet_index(".", tampered)

    assert validation["fresh"] is False
    assert validation["status"] == "stale"
    assert "bundle_digest_mismatch" in validation["reasons"]
    assert "packets_mismatch" in validation["reasons"]


def test_current_human_decision_is_reported_without_generating_new_template(monkeypatch) -> None:
    workflow = ".github/workflows/example.yml"
    entry = {
        "review_id": decision_record.review_id_for_workflow(workflow),
        "workflow": workflow,
        "workflow_sha256": "a" * 64,
        "permission_group": "repository_mutation",
        "granted_write_scopes": ["contents: write"],
        "inferred_permission_reasons": ["reviewed reason"],
        "required_human_evidence": ["reviewed proof"],
        "review_state": "human_decision_recorded",
        "human_decision_recorded": True,
        "human_decision": "keep",
        "allowed_decisions": ["keep", "reduce", "split", "defer"],
        "decision_evidence_refs": [],
        "decision_record_ref": "docs/ci/workflow-permission-decisions/example.decision.json",
        "decision_record_refs": ["docs/ci/workflow-permission-decisions/example.decision.json"],
        "proof_contract": ["exact-head CI"],
        "rollback_contract": {
            "strategy": "restore_exact_workflow_bytes",
            "workflow_sha256": "a" * 64,
        },
        "requires_human_review": True,
        "next_allowed_action": "retain_current_permissions",
    }
    fake_plane = {
        "input_provenance": {"input_digest": "fake-control-plane-digest"},
        "review_queue": [entry],
    }
    monkeypatch.setattr(
        review_packet,
        "build_workflow_permission_review_control_plane",
        lambda _root: fake_plane,
    )

    payload = review_packet.build_workflow_permission_review_packet_index(".")
    packet = payload["packets"][0]

    assert payload["summary"]["human_decision_recorded_count"] == 1
    assert payload["summary"]["pending_human_review_count"] == 0
    assert packet["decision_boundary"]["current_human_decision"] == "keep"
    assert packet["decision_boundary"]["decision_record_template"] is None
    assert packet["safe_to_patch"] is False
    assert not any(packet["authority_boundary"].values())


def test_empty_review_queue_is_not_required(monkeypatch) -> None:
    fake_plane = {
        "input_provenance": {"input_digest": "empty-control-plane-digest"},
        "review_queue": [],
    }
    monkeypatch.setattr(
        review_packet,
        "build_workflow_permission_review_control_plane",
        lambda _root: fake_plane,
    )

    payload = review_packet.build_workflow_permission_review_packet_index(".")

    assert payload["status"] == "not_required"
    assert payload["summary"]["packet_count"] == 0
    assert payload["summary"]["decision_template_count"] == 0
    assert payload["packets"] == []
    assert payload["packet_index"] == []


def test_markdown_keeps_review_first_boundary_visible() -> None:
    payload = review_packet.build_workflow_permission_review_packet_index(".")
    packet = payload["packets"][0]
    markdown = review_packet.render_packet_markdown(packet)
    index_markdown = review_packet.render_index_markdown(payload)

    assert "Generated evidence only" in markdown
    assert "does **not** choose or recommend a decision" in markdown
    assert "permission_mutation_allowed=false" in markdown
    assert "No packet is a human decision" in index_markdown
    assert f"`{payload['bundle_digest']}`" in index_markdown
