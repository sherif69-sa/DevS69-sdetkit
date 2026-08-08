from __future__ import annotations

import copy
from pathlib import Path

import pytest

from sdetkit import workflow_permission_review_handoff_bundle as handoff


def _zero_boundary() -> dict[str, bool]:
    return {"workflow_mutation_allowed": False, "permission_mutation_allowed": False}


def _work_item(
    *,
    review_id: str = "review-example",
    workflow: str = ".github/workflows/example.yml",
    packet_digest: str = "packet-marker",
) -> dict[str, object]:
    return {
        "work_item_id": f"work-{review_id}",
        "review_id": review_id,
        "workflow": workflow,
        "workflow_sha256": "workflow-marker",
        "permission_group": "repository_mutation",
        "lifecycle_state": "pending_human_review",
        "next_human_action": "complete_human_permission_review",
        "packet_id": f"packet-{review_id}",
        "packet_digest": packet_digest,
        "machine_recommendation": None,
        "review_priority": None,
        "reviewer_assignment": None,
        "decision_prefill": None,
        "safe_to_patch": False,
        "authority_boundary": _zero_boundary(),
    }


def _worklist(
    items: list[dict[str, object]], *, status: str = "human_work_required"
) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.workflow_permission_review_worklist.v1",
        "status": status,
        "input_provenance": {"input_digest": "worklist-input-marker"},
        "summary": {
            "work_item_count": len(items),
            "review_action_count": len(items),
            "implementation_action_count": 0,
            "blocked_repair_count": 0,
        },
        "bundle_digest": "worklist-bundle-marker",
        "work_items": items,
        "authority_boundary": _zero_boundary(),
    }


def _packet(
    *,
    review_id: str = "review-example",
    workflow: str = ".github/workflows/example.yml",
    packet_digest: str = "packet-marker",
) -> dict[str, object]:
    return {
        "packet_id": f"packet-{review_id}",
        "review_id": review_id,
        "workflow": workflow,
        "workflow_sha256": "workflow-marker",
        "permission_group": "repository_mutation",
        "review_state": "pending_human_review",
        "packet_digest": packet_digest,
        "safe_to_patch": False,
        "current_permissions": {"write_scopes": ["contents: write"]},
        "evidence": {
            "retained_evidence_refs": [],
            "required_human_evidence": ["confirm the reviewed write-scope need"],
        },
        "decision_boundary": {
            "allowed_decisions": ["keep", "reduce", "split", "defer"],
        },
        "proof_contract": ["exact-head proof"],
        "authority_boundary": _zero_boundary(),
    }


def _packet_index(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.workflow_permission_review_packet.v1",
        "status": "human_review_required" if items else "not_required",
        "input_provenance": {"input_digest": "packet-input-marker"},
        "bundle_digest": "packet-bundle-marker",
        "packets": items,
    }


def _install_inputs(
    monkeypatch: pytest.MonkeyPatch,
    worklist_payload: dict[str, object],
    packet_payload: dict[str, object],
) -> None:
    monkeypatch.setattr(
        handoff,
        "build_workflow_permission_review_worklist",
        lambda _root: worklist_payload,
    )
    monkeypatch.setattr(
        handoff,
        "build_workflow_permission_review_packet_index",
        lambda _root: packet_payload,
    )


def test_active_work_item_packages_only_exact_current_packet(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item = _work_item()
    packet = _packet()
    _install_inputs(monkeypatch, _worklist([item]), _packet_index([packet]))

    manifest, files = handoff._build_current_bundle(tmp_path)

    assert manifest["status"] == "ready_for_human_handoff"
    assert manifest["summary"]["active_work_item_count"] == 1
    assert manifest["summary"]["packaged_packet_count"] == 1
    assert manifest["global_reasons"] == []
    assert [ref["review_id"] for ref in manifest["packet_refs"]] == ["review-example"]
    assert "packets/review-example.json" in files
    assert "packets/review-example.md" in files
    assert handoff.WORKLIST_JSON_NAME in files
    assert handoff.WORKLIST_TEXT_NAME in files
    assert handoff.README_NAME in files
    assert manifest["summary"]["artifact_count"] == len(files)
    assert manifest["summary"]["machine_recommendation_count"] == 0
    assert manifest["summary"]["automatic_decision_count"] == 0
    assert not any(manifest["authority_boundary"].values())


def test_no_active_work_is_not_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(monkeypatch, _worklist([], status="not_required"), _packet_index([]))

    manifest = handoff.build_workflow_permission_review_handoff_bundle(tmp_path)

    assert manifest["status"] == "not_required"
    assert manifest["summary"]["active_work_item_count"] == 0
    assert manifest["summary"]["packaged_packet_count"] == 0
    assert manifest["packet_refs"] == []


def test_missing_packet_blocks_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(monkeypatch, _worklist([_work_item()]), _packet_index([]))

    manifest = handoff.build_workflow_permission_review_handoff_bundle(tmp_path)

    assert manifest["status"] == "blocked"
    assert "review-example:packet_missing" in manifest["global_reasons"]
    assert "active_packet_count_mismatch" in manifest["global_reasons"]
    with pytest.raises(ValueError, match="blocked reviewer handoff bundle"):
        handoff.write_workflow_permission_review_handoff_bundle(
            tmp_path,
            "build/handoff",
        )
    assert not (tmp_path / "build" / "handoff").exists()


def test_duplicate_packets_block_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    packet = _packet()
    _install_inputs(
        monkeypatch, _worklist([_work_item()]), _packet_index([packet, copy.deepcopy(packet)])
    )

    manifest = handoff.build_workflow_permission_review_handoff_bundle(tmp_path)

    assert manifest["status"] == "blocked"
    assert "review-example:duplicate_packets" in manifest["global_reasons"]


def test_packet_digest_mismatch_blocks_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(
        monkeypatch,
        _worklist([_work_item(packet_digest="worklist-packet-marker")]),
        _packet_index([_packet(packet_digest="current-packet-marker")]),
    )

    manifest = handoff.build_workflow_permission_review_handoff_bundle(tmp_path)

    assert manifest["status"] == "blocked"
    assert "review-example:packet_binding_mismatch:packet_digest" in manifest["global_reasons"]


def test_machine_field_or_authority_escalation_blocks_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item = _work_item()
    item["review_priority"] = 1
    packet = _packet()
    packet["safe_to_patch"] = True
    _install_inputs(monkeypatch, _worklist([item]), _packet_index([packet]))

    manifest = handoff.build_workflow_permission_review_handoff_bundle(tmp_path)

    assert manifest["status"] == "blocked"
    assert (
        "review-example:work_item_machine_field_not_null:review_priority"
        in manifest["global_reasons"]
    )
    assert "review-example:packet_safe_to_patch_not_false" in manifest["global_reasons"]


def test_bundle_files_and_manifest_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    items = [
        _work_item(review_id="review-b", workflow=".github/workflows/b.yml"),
        _work_item(review_id="review-a", workflow=".github/workflows/a.yml"),
    ]
    packets = [
        _packet(review_id="review-b", workflow=".github/workflows/b.yml"),
        _packet(review_id="review-a", workflow=".github/workflows/a.yml"),
    ]
    _install_inputs(monkeypatch, _worklist(items), _packet_index(packets))

    first_manifest, first_files = handoff._build_current_bundle(tmp_path)
    second_manifest, second_files = handoff._build_current_bundle(tmp_path)

    assert first_manifest == second_manifest
    assert first_files == second_files
    assert [ref["workflow"] for ref in first_manifest["packet_refs"]] == [
        ".github/workflows/a.yml",
        ".github/workflows/b.yml",
    ]


def test_writer_and_validator_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(monkeypatch, _worklist([_work_item()]), _packet_index([_packet()]))

    written = handoff.write_workflow_permission_review_handoff_bundle(
        tmp_path,
        "build/handoff",
    )
    validation = handoff.validate_workflow_permission_review_handoff_bundle(
        tmp_path,
        "build/handoff",
    )

    assert written["status"] == "ready_for_human_handoff"
    assert validation["status"] == "fresh"
    assert validation["fresh"] is True
    assert validation["reasons"] == []
    assert not any(validation["authority_boundary"].values())


def test_validator_detects_tampered_packet_and_unexpected_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(monkeypatch, _worklist([_work_item()]), _packet_index([_packet()]))
    bundle = tmp_path / "build" / "handoff"
    handoff.write_workflow_permission_review_handoff_bundle(tmp_path, bundle)
    packet_path = bundle / "packets" / "review-example.json"
    packet_path.write_text(
        packet_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8"
    )
    (bundle / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

    validation = handoff.validate_workflow_permission_review_handoff_bundle(tmp_path, bundle)

    assert validation["fresh"] is False
    assert "artifact_content_mismatch:packets/review-example.json" in validation["reasons"]
    assert "artifact_digest_mismatch:packets/review-example.json" in validation["reasons"]
    assert "artifact_unexpected:unexpected.txt" in validation["reasons"]


def test_validator_detects_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_inputs(monkeypatch, _worklist([_work_item()]), _packet_index([_packet()]))
    bundle = tmp_path / "build" / "handoff"
    handoff.write_workflow_permission_review_handoff_bundle(tmp_path, bundle)
    (bundle / "packets" / "review-example.md").unlink()

    validation = handoff.validate_workflow_permission_review_handoff_bundle(tmp_path, bundle)

    assert validation["fresh"] is False
    assert "artifact_missing:packets/review-example.md" in validation["reasons"]


def test_validator_detects_upstream_worklist_staleness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    initial_worklist = _worklist([_work_item()])
    packets = _packet_index([_packet()])
    _install_inputs(monkeypatch, initial_worklist, packets)
    bundle = tmp_path / "build" / "handoff"
    handoff.write_workflow_permission_review_handoff_bundle(tmp_path, bundle)

    changed = copy.deepcopy(initial_worklist)
    changed["bundle_digest"] = "new-worklist-bundle-marker"
    _install_inputs(monkeypatch, changed, packets)

    validation = handoff.validate_workflow_permission_review_handoff_bundle(tmp_path, bundle)

    assert validation["fresh"] is False
    assert "bundle_digest_mismatch" in validation["reasons"]
    assert "input_digest_mismatch" in validation["reasons"]


def test_output_guard_and_non_empty_directory_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _install_inputs(monkeypatch, _worklist([_work_item()]), _packet_index([_packet()]))

    assert (
        handoff._safe_output_dir(root, Path("build/handoff"))
        == (root / "build" / "handoff").resolve()
    )
    with pytest.raises(ValueError, match="may only be written under build"):
        handoff._safe_output_dir(root, Path("docs/ci/handoff"))

    occupied = root / "build" / "occupied"
    occupied.mkdir(parents=True)
    (occupied / "human-note.txt").write_text("retain me\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be absent or empty"):
        handoff.write_workflow_permission_review_handoff_bundle(root, occupied)
    assert (occupied / "human-note.txt").read_text(encoding="utf-8") == "retain me\n"


def test_live_repository_handoff_never_grants_human_or_merge_authority() -> None:
    manifest = handoff.build_workflow_permission_review_handoff_bundle(".")

    assert manifest["summary"]["machine_recommendation_count"] == 0
    assert manifest["summary"]["machine_priority_count"] == 0
    assert manifest["summary"]["automatic_reviewer_assignment_count"] == 0
    assert manifest["summary"]["automatic_decision_count"] == 0
    assert manifest["summary"]["automatic_permission_change_count"] == 0
    assert not any(manifest["authority_boundary"].values())
