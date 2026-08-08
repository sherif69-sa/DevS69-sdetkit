from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sdetkit import workflow_permission_decision_record as decision_record
from sdetkit import workflow_permission_review_packet as review_packet
from sdetkit import workflow_permission_review_session as review_session


def _packet(
    workflow: str,
    *,
    digest: str,
    decided: bool = False,
) -> dict[str, object]:
    review_id = decision_record.review_id_for_workflow(workflow)
    workflow_sha256 = ("a" if "one" in workflow else "b") * 64
    return {
        "schema_version": review_packet.SCHEMA_VERSION,
        "packet_id": f"packet-{review_id}",
        "review_id": review_id,
        "workflow": workflow,
        "workflow_sha256": workflow_sha256,
        "permission_group": "repository_mutation",
        "review_state": "human_decision_recorded" if decided else "pending_human_review",
        "packet_digest": digest,
        "decision_boundary": {
            "human_decision_recorded": decided,
            "current_human_decision": "keep" if decided else None,
        },
        "proof_contract": ["exact-head CI", "workflow-specific execution proof"],
        "rollback_contract": {
            "strategy": "restore_exact_workflow_bytes",
            "workflow_sha256": workflow_sha256,
        },
    }


def _packet_index(*, second_decided: bool = False) -> dict[str, object]:
    packets = [
        _packet(".github/workflows/one.yml", digest="packet-one"),
        _packet(".github/workflows/two.yml", digest="packet-two", decided=second_decided),
    ]
    return {
        "schema_version": review_packet.SCHEMA_VERSION,
        "bundle_digest": "bundle-current",
        "input_provenance": {"input_digest": "input-current"},
        "packets": packets,
    }


def _session_entry(packet: dict[str, object], *, decision: str = "keep") -> dict[str, object]:
    proposed_change: dict[str, object]
    if decision in {"keep", "defer"}:
        proposed_change = {"kind": "none"}
    else:
        proposed_change = {
            "kind": "permission_only",
            "summary": "Use the reviewed narrower job-local write scope.",
            "evidence_ref": "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181",
        }
    return {
        "review_id": packet["review_id"],
        "packet_digest": packet["packet_digest"],
        "workflow": packet["workflow"],
        "workflow_sha256": packet["workflow_sha256"],
        "permission_group": packet["permission_group"],
        "decision": decision,
        "rationale": "I reviewed the exact workflow evidence and made this decision.",
        "proposed_change": proposed_change,
        "proof_acknowledged": True,
        "rollback_acknowledged": True,
    }


def _session(
    packet_index: dict[str, object],
    *,
    mode: str = "partial",
    entries: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    packets = packet_index["packets"]
    assert isinstance(packets, list)
    if entries is None:
        first = packets[0]
        assert isinstance(first, dict)
        entries = [_session_entry(first)]
    return {
        "schema_version": review_session.SCHEMA_VERSION,
        "session_mode": mode,
        "packet_bundle_digest": packet_index["bundle_digest"],
        "packet_input_digest": packet_index["input_provenance"]["input_digest"],
        "reviewer": "repository-owner",
        "reviewer_evidence": "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181#issuecomment-1",
        "decided_at": "2026-08-08T15:00:00+00:00",
        "entries": entries,
        "authority_boundary": review_session.authority_boundary(),
    }


def _install_packet_index(monkeypatch, packet_index: dict[str, object]) -> None:
    monkeypatch.setattr(
        review_session,
        "build_workflow_permission_review_packet_index",
        lambda _root: packet_index,
    )


def test_live_complete_template_binds_every_pending_packet_without_deciding() -> None:
    packet_index = review_packet.build_workflow_permission_review_packet_index(".")
    template = review_session.build_review_session_template(".", mode="complete")
    pending = [
        packet
        for packet in packet_index["packets"]
        if packet["decision_boundary"]["human_decision_recorded"] is False
    ]

    assert template["packet_bundle_digest"] == packet_index["bundle_digest"]
    assert template["packet_input_digest"] == packet_index["input_provenance"]["input_digest"]
    assert len(template["entries"]) == len(pending)
    assert template["reviewer"] is None
    assert template["reviewer_evidence"] is None
    assert template["decided_at"] is None
    assert not any(template["authority_boundary"].values())
    for entry in template["entries"]:
        assert entry["decision"] is None
        assert entry["rationale"] is None
        assert entry["proposed_change"] is None
        assert entry["proof_acknowledged"] is False
        assert entry["rollback_acknowledged"] is False


def test_blank_generated_template_is_intentionally_invalid() -> None:
    template = review_session.build_review_session_template(".", mode="complete")
    validation = review_session.validate_review_session(".", template)

    assert validation["valid_current"] is False
    assert validation["status"] == "invalid"
    assert "reviewer_missing" in validation["invalid_reasons"]
    assert "reviewer_evidence_missing" in validation["invalid_reasons"]
    assert "decided_at_invalid" in validation["invalid_reasons"]
    assert validation["compiled_candidates"] == []


def test_valid_partial_session_compiles_only_explicit_human_entry(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "compiled"
    assert compilation["compiled_record_count"] == 1
    assert len(compilation["records"]) == 1
    record = compilation["records"][0]["record"]
    assert record["decision"] == "keep"
    assert record["reviewer"] == session["reviewer"]
    assert record["rationale"] == session["entries"][0]["rationale"]
    assert not any(record["authority_boundary"].values())
    assert not any(compilation["authority_boundary"].values())


def test_valid_reduce_session_is_revalidated_by_decision_record_v1(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    packets = packet_index["packets"]
    assert isinstance(packets, list)
    first = packets[0]
    assert isinstance(first, dict)
    session = _session(packet_index, entries=[_session_entry(first, decision="reduce")])

    compilation = review_session.compile_review_session(".", session)
    record = compilation["records"][0]["record"]
    review_entry = {
        "review_id": first["review_id"],
        "workflow": first["workflow"],
        "workflow_sha256": first["workflow_sha256"],
        "permission_group": first["permission_group"],
    }
    validation = decision_record.validate_decision_record(record, review_entry)

    assert validation["valid_current"] is True
    assert validation["reasons"] == []
    assert record["proposed_change"]["kind"] == "permission_only"


def test_complete_session_requires_every_pending_packet(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index, mode="complete")

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["compiled_record_count"] == 0
    assert compilation["records"] == []
    missing = compilation["validation"]["missing_review_ids"]
    assert len(missing) == 1
    assert f"complete_session_missing:{missing[0]}" in compilation["validation"]["invalid_reasons"]


def test_complete_session_compiles_all_pending_packets_when_explicit(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    packets = packet_index["packets"]
    assert isinstance(packets, list)
    entries = [_session_entry(packet) for packet in packets if isinstance(packet, dict)]
    session = _session(packet_index, mode="complete", entries=entries)

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "compiled"
    assert compilation["compiled_record_count"] == 2
    assert compilation["validation"]["missing_review_ids"] == []


def test_stale_bundle_blocks_all_records(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)
    session["packet_bundle_digest"] = "old-bundle"

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    assert compilation["validation"]["status"] == "stale"
    assert compilation["validation"]["stale_reasons"] == ["packet_bundle_digest_mismatch"]


def test_stale_packet_binding_blocks_all_records(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)
    session["entries"][0]["packet_digest"] = "old-packet"

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    reasons = compilation["validation"]["stale_reasons"]
    assert any(reason.startswith("packet_digest_mismatch:") for reason in reasons)


def test_duplicate_review_id_is_conflict_not_latest_wins(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    packets = packet_index["packets"]
    assert isinstance(packets, list)
    first = packets[0]
    assert isinstance(first, dict)
    entry = _session_entry(first)
    session = _session(packet_index, entries=[entry, copy.deepcopy(entry)])

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    assert any(
        reason.startswith("duplicate_review_id:")
        for reason in compilation["validation"]["invalid_reasons"]
    )


def test_already_decided_packet_cannot_be_reviewed_again(monkeypatch) -> None:
    packet_index = _packet_index(second_decided=True)
    _install_packet_index(monkeypatch, packet_index)
    packets = packet_index["packets"]
    assert isinstance(packets, list)
    second = packets[1]
    assert isinstance(second, dict)
    session = _session(packet_index, entries=[_session_entry(second)])

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    assert (
        f"review_already_decided:{second['review_id']}"
        in compilation["validation"]["invalid_reasons"]
    )


def test_missing_proof_or_rollback_acknowledgement_blocks_session(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)
    session["entries"][0]["proof_acknowledged"] = False
    session["entries"][0]["rollback_acknowledged"] = False

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    reasons = compilation["validation"]["invalid_reasons"]
    assert any(reason.startswith("proof_not_acknowledged:") for reason in reasons)
    assert any(reason.startswith("rollback_not_acknowledged:") for reason in reasons)


def test_invalid_decision_record_fields_block_entire_session(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)
    session["entries"][0]["rationale"] = ""

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    assert any(
        reason.endswith(":rationale_missing")
        for reason in compilation["validation"]["invalid_reasons"]
    )


def test_session_digest_is_deterministic_and_changes_with_human_input(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)

    first = review_session.session_digest(session)
    second = review_session.session_digest(copy.deepcopy(session))
    changed = copy.deepcopy(session)
    changed["entries"][0]["rationale"] = "Different reviewed rationale."

    assert first == second
    assert first != review_session.session_digest(changed)


def test_compilation_manifest_binds_session_and_record_hashes(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)

    compilation = review_session.compile_review_session(".", session)
    manifest = compilation["manifest"]
    record_item = compilation["records"][0]

    assert manifest["session_digest"] == review_session.session_digest(session)
    assert manifest["packet_bundle_digest"] == packet_index["bundle_digest"]
    assert manifest["compiled_record_count"] == 1
    assert manifest["records"][0]["record_sha256"] == record_item["record_sha256"]
    assert manifest["canonical_decision_directory_write_allowed"] is False
    assert manifest["source_tree_write_allowed"] is False
    assert manifest["implementation_authorized"] is False
    assert not any(manifest["authority_boundary"].values())


def test_writer_allows_external_output_but_never_grants_source_write(
    monkeypatch, tmp_path: Path
) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    compilation = review_session.compile_review_session(".", _session(packet_index))

    result = review_session.write_compiled_decision_records(".", tmp_path, compilation)

    assert result["written_record_count"] == 1
    assert Path(result["manifest_path"]).is_file()
    record_path = Path(result["written_records"][0])
    assert record_path.is_file()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["decision"] == "keep"
    assert result["source_tree_write_allowed"] is False
    assert not any(result["authority_boundary"].values())


def test_writer_refuses_canonical_decision_directory(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    compilation = review_session.compile_review_session(".", _session(packet_index))

    with pytest.raises(ValueError, match="only be written under build"):
        review_session.write_compiled_decision_records(
            ".",
            "docs/ci/workflow-permission-decisions",
            compilation,
        )


def test_authority_escalation_blocks_session(monkeypatch) -> None:
    packet_index = _packet_index()
    _install_packet_index(monkeypatch, packet_index)
    session = _session(packet_index)
    session["authority_boundary"]["permission_mutation_allowed"] = True

    compilation = review_session.compile_review_session(".", session)

    assert compilation["status"] == "blocked"
    assert compilation["records"] == []
    assert "authority_boundary_mismatch" in compilation["validation"]["invalid_reasons"]


def test_zero_pending_packets_are_not_required(monkeypatch) -> None:
    packet_index = _packet_index(second_decided=True)
    packets = packet_index["packets"]
    assert isinstance(packets, list)
    first = packets[0]
    assert isinstance(first, dict)
    first["decision_boundary"]["human_decision_recorded"] = True
    _install_packet_index(monkeypatch, packet_index)

    template = review_session.build_review_session_template(".", mode="complete")
    validation = review_session.validate_review_session(".", template)
    compilation = review_session.compile_review_session(".", template)

    assert template["entries"] == []
    assert validation["status"] == "not_required"
    assert validation["valid_current"] is False
    assert validation["pending_packet_count"] == 0
    assert validation["invalid_reasons"] == []
    assert validation["stale_reasons"] == []
    assert compilation["status"] == "not_required"
    assert compilation["compiled_record_count"] == 0
    assert compilation["records"] == []
    assert not any(compilation["authority_boundary"].values())
