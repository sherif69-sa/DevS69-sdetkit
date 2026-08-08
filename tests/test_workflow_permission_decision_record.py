from __future__ import annotations

import json
from pathlib import Path

from sdetkit import workflow_permission_decision_record as decision_record
from sdetkit import workflow_permission_review_control_plane as control_plane


def _review_entry() -> dict[str, object]:
    return {
        "review_id": "wpr-0123456789abcdef",
        "workflow": ".github/workflows/security-maintenance-bot.yml",
        "workflow_sha256": "a" * 64,
        "permission_group": "security_upload",
    }


def _record(
    review: dict[str, object] | None = None,
    *,
    decision: str = "split",
) -> dict[str, object]:
    review = review or _review_entry()
    workflow_sha256 = str(review["workflow_sha256"])
    proposed_change: dict[str, object]
    if decision in {"keep", "defer"}:
        proposed_change = {"kind": "none"}
    else:
        proposed_change = {
            "kind": "permission_only",
            "summary": "Move write scopes to the jobs that actually use them.",
            "evidence_ref": "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181#issuecomment-1",
        }
    return {
        "schema_version": decision_record.SCHEMA_VERSION,
        "review_id": review["review_id"],
        "workflow": review["workflow"],
        "workflow_sha256": workflow_sha256,
        "permission_group": review["permission_group"],
        "decision": decision,
        "reviewer": "repository-owner",
        "reviewer_evidence": "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181#issuecomment-2",
        "decided_at": "2026-08-08T13:30:00+00:00",
        "rationale": "The reviewed workflow scopes are broader than the job-local operations require.",
        "proposed_change": proposed_change,
        "proof_contract": [
            "workflow permission contract tests",
            "exact-head CI",
            "manual workflow_dispatch proof",
        ],
        "rollback_contract": {
            "strategy": "restore_exact_workflow_bytes",
            "workflow_sha256": workflow_sha256,
        },
        "authority_boundary": decision_record.authority_boundary(),
    }


def _write_record(root: Path, name: str, payload: dict[str, object] | str) -> Path:
    directory = root / decision_record.DECISION_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_valid_exact_decision_record_is_current() -> None:
    review = _review_entry()
    validation = decision_record.validate_decision_record(_record(review), review)

    assert validation["status"] == "current"
    assert validation["valid_current"] is True
    assert validation["stale"] is False
    assert validation["reasons"] == []
    assert validation["decision"] == "split"
    assert not any(validation["authority_boundary"].values())


def test_workflow_digest_change_makes_record_stale() -> None:
    review = _review_entry()
    record = _record(review)
    record["workflow_sha256"] = "b" * 64
    rollback = record["rollback_contract"]
    assert isinstance(rollback, dict)
    rollback["workflow_sha256"] = "b" * 64

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "stale"
    assert validation["valid_current"] is False
    assert validation["stale"] is True
    assert validation["reasons"] == [
        "rollback_workflow_digest_mismatch",
        "workflow_digest_mismatch",
    ]


def test_review_id_mismatch_is_invalid() -> None:
    review = _review_entry()
    record = _record(review)
    record["review_id"] = "wpr-wrong"

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "invalid"
    assert "review_id_mismatch" in validation["reasons"]


def test_permission_group_mismatch_is_invalid() -> None:
    review = _review_entry()
    record = _record(review)
    record["permission_group"] = "repository_mutation"

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "invalid"
    assert "permission_group_mismatch" in validation["reasons"]


def test_reviewer_evidence_is_required_and_must_be_github_url() -> None:
    review = _review_entry()
    missing = _record(review)
    missing["reviewer_evidence"] = ""
    invalid_url = _record(review)
    invalid_url["reviewer_evidence"] = "https://example.com/review"

    missing_validation = decision_record.validate_decision_record(missing, review)
    invalid_validation = decision_record.validate_decision_record(invalid_url, review)

    assert "reviewer_evidence_missing" in missing_validation["reasons"]
    assert "reviewer_evidence_must_be_github_url" in invalid_validation["reasons"]


def test_naive_decision_timestamp_is_invalid() -> None:
    review = _review_entry()
    record = _record(review)
    record["decided_at"] = "2026-08-08T13:30:00"

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "invalid"
    assert "decided_at_invalid" in validation["reasons"]


def test_reduce_or_split_requires_permission_only_change() -> None:
    review = _review_entry()
    record = _record(review, decision="split")
    record["proposed_change"] = {"kind": "none"}

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "invalid"
    assert "proposed_change_must_be_permission_only" in validation["reasons"]


def test_keep_or_defer_must_not_smuggle_permission_change() -> None:
    review = _review_entry()
    record = _record(review, decision="keep")
    record["proposed_change"] = {
        "kind": "permission_only",
        "summary": "Hidden change",
        "evidence_ref": "https://github.com/sherif69-sa/DevS69-sdetkit/issues/2181",
    }

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "invalid"
    assert "proposed_change_must_be_none" in validation["reasons"]


def test_authority_escalation_in_record_is_invalid() -> None:
    review = _review_entry()
    record = _record(review)
    boundary = record["authority_boundary"]
    assert isinstance(boundary, dict)
    boundary["implementation_authorized"] = True

    validation = decision_record.validate_decision_record(record, review)

    assert validation["status"] == "invalid"
    assert validation["reasons"] == ["authority_boundary_mismatch"]


def test_duplicate_current_records_are_conflict_and_neither_wins(tmp_path: Path) -> None:
    review = _review_entry()
    _write_record(tmp_path, "one.decision.json", _record(review))
    _write_record(tmp_path, "two.decision.json", _record(review))

    index = decision_record.build_decision_record_index(tmp_path, [review])

    assert index["record_count"] == 2
    assert index["current_decision_count"] == 0
    assert index["conflict_workflow_count"] == 1
    assert index["conflict_workflows"] == [review["workflow"]]
    assert index["current_by_workflow"] == {}
    assert index["status_counts"] == {"conflict": 2}
    assert all(item["status"] == "conflict" for item in index["records"])


def test_malformed_json_is_invalid(tmp_path: Path) -> None:
    _write_record(tmp_path, "broken.decision.json", "{not-json\n")

    index = decision_record.build_decision_record_index(tmp_path, [_review_entry()])

    assert index["status_counts"] == {"invalid": 1}
    assert index["records"][0]["reasons"] == ["record_json_invalid"]


def test_unknown_workflow_record_is_invalid(tmp_path: Path) -> None:
    record = _record()
    record["workflow"] = ".github/workflows/unknown.yml"
    _write_record(tmp_path, "unknown.decision.json", record)

    index = decision_record.build_decision_record_index(tmp_path, [_review_entry()])

    assert index["status_counts"] == {"invalid": 1}
    assert index["records"][0]["reasons"] == ["workflow_not_in_review_queue"]


def test_decision_index_text_keeps_zero_implementation_authority(tmp_path: Path) -> None:
    review = _review_entry()
    _write_record(tmp_path, "current.decision.json", _record(review))

    index = decision_record.build_decision_record_index(tmp_path, [review])
    text = decision_record.render_decision_record_index_text(index)

    assert index["current_decision_count"] == 1
    assert not any(index["authority_boundary"].values())
    assert "implementation_authorized=false" in text
    assert "workflow_mutation_allowed=false" in text
    assert "merge_authorized=false" in text


def test_live_repository_has_no_machine_decision_records_yet() -> None:
    payload = control_plane.build_workflow_permission_review_control_plane(".")

    assert payload["summary"]["permission_review_count"] == 16
    assert payload["summary"]["decision_record_count"] == 0
    assert payload["summary"]["current_decision_record_count"] == 0
    assert payload["summary"]["human_decision_recorded_count"] == 0
    assert payload["summary"]["pending_human_review_count"] == 16
    assert all(entry["human_decision_recorded"] is False for entry in payload["review_queue"])
    assert all(entry["safe_to_patch"] is False for entry in payload["review_queue"])
