from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from sdetkit.trusted_test_observation_classification import (
    CLASSIFICATION_JSON,
    CLASSIFICATION_MD,
    SCHEMA_VERSION,
    STATUS,
    build_trusted_observation_classification,
    main,
    read_observation_history_records,
    render_classification_markdown,
    validate_classification_report,
)
from sdetkit.trusted_test_observation_history import (
    build_observation_history_record,
)

FINGERPRINT_A = "a" * 64
FINGERPRINT_B = "b" * 64
FINGERPRINT_C = "c" * 64
FINGERPRINT_D = "d" * 64
HEAD_A = "1" * 40
HEAD_B = "2" * 40


def _report(
    *,
    run_id: str,
    head_sha: str,
    observations: list[dict[str, str]],
) -> dict:
    counts = {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "skipped": 0,
    }
    for observation in observations:
        counts[observation["outcome"]] += 1
    return {
        "schema_version": "sdetkit.trusted_test_observation_capture.v1",
        "status": "trusted_main_observations_captured",
        "source": {
            "workflow": "CI",
            "job": "Full CI lane",
            "run_id": run_id,
            "head_sha": head_sha,
            "event_name": "push",
            "ref_name": "refs/heads/main",
            "trusted_main": True,
            "input_read_only": True,
            "commands_executed_by_reader": False,
        },
        "summary": {
            "observation_count": len(observations),
            **counts,
            "flaky_classification_performed": False,
            "raw_test_identity_emitted": False,
        },
        "observations": observations,
        "decision_boundary": {
            "raw_observation_only": True,
            "flaky_classification_performed": False,
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _record(
    *,
    run_id: str,
    head_sha: str,
    recorded_at: str,
    observations: list[dict[str, str]],
) -> dict:
    return build_observation_history_record(
        _report(
            run_id=run_id,
            head_sha=head_sha,
            observations=observations,
        ),
        source_run_id=run_id,
        source_head_sha=head_sha,
        recorded_at_utc=recorded_at,
    )


def _records() -> list[dict]:
    return [
        _record(
            run_id="run-a",
            head_sha=HEAD_A,
            recorded_at="2026-06-16T00:00:00Z",
            observations=[
                {"test_fingerprint": FINGERPRINT_A, "outcome": "failed"},
                {"test_fingerprint": FINGERPRINT_B, "outcome": "passed"},
                {"test_fingerprint": FINGERPRINT_C, "outcome": "error"},
                {"test_fingerprint": FINGERPRINT_D, "outcome": "skipped"},
            ],
        ),
        _record(
            run_id="run-b",
            head_sha=HEAD_B,
            recorded_at="2026-06-16T01:00:00Z",
            observations=[
                {"test_fingerprint": FINGERPRINT_A, "outcome": "passed"},
                {"test_fingerprint": FINGERPRINT_B, "outcome": "passed"},
                {"test_fingerprint": FINGERPRINT_C, "outcome": "failed"},
                {"test_fingerprint": FINGERPRINT_D, "outcome": "skipped"},
            ],
        ),
    ]


def test_classifies_fingerprints_with_bound_provenance_without_identity_projection() -> None:
    report = build_trusted_observation_classification(_records())

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == STATUS
    assert report["source"]["record_count"] == 2
    assert report["source"]["source_run_ids"] == ["run-a", "run-b"]
    assert report["source"]["source_head_shas"] == [HEAD_A, HEAD_B]
    assert report["source"]["per_observation_provenance_bound"] is True

    classifications = {item["test_fingerprint"]: item for item in report["classifications"]}
    flaky = classifications[FINGERPRINT_A]
    assert flaky["classification"] == "flaky"
    assert flaky["passed"] == 1
    assert flaky["failed"] == 1
    assert flaky["decision"] == "instability_context_only"
    assert flaky["observation_provenance"] == [
        {
            "source_run_id": "run-a",
            "source_head_sha": HEAD_A,
            "outcome": "failed",
        },
        {
            "source_run_id": "run-b",
            "source_head_sha": HEAD_B,
            "outcome": "passed",
        },
    ]
    assert classifications[FINGERPRINT_B]["classification"] == "stable-passing"
    assert classifications[FINGERPRINT_C]["classification"] == "stable-failing"
    assert classifications[FINGERPRINT_D]["classification"] == "insufficient-history"

    serialized = json.dumps(report, sort_keys=True)
    assert '"test_id"' not in serialized
    assert '"classname"' not in serialized
    assert '"nodeid"' not in serialized
    assert FINGERPRINT_A in serialized


def test_policy_treats_skipped_as_non_decisive() -> None:
    records = [
        _record(
            run_id="run-a",
            head_sha=HEAD_A,
            recorded_at="2026-06-16T00:00:00Z",
            observations=[{"test_fingerprint": FINGERPRINT_A, "outcome": "passed"}],
        ),
        _record(
            run_id="run-b",
            head_sha=HEAD_B,
            recorded_at="2026-06-16T01:00:00Z",
            observations=[{"test_fingerprint": FINGERPRINT_A, "outcome": "skipped"}],
        ),
    ]
    item = build_trusted_observation_classification(records)["classifications"][0]
    assert item["classification"] == "insufficient-history"
    assert item["decisive_observation_count"] == 1
    assert item["passed"] == 1
    assert item["skipped"] == 1


def test_empty_history_is_valid_fail_closed_advisory_output() -> None:
    report = build_trusted_observation_classification([])
    assert report["classifications"] == []
    assert report["summary"]["fingerprint_count"] == 0
    assert report["summary"]["flaky"] == 0
    assert report["decision_boundary"]["advisory_only"] is True
    assert report["decision_boundary"]["current_pr_decision_input"] is False


def test_classification_is_deterministic() -> None:
    records = _records()
    first = build_trusted_observation_classification(records)
    second = build_trusted_observation_classification(deepcopy(records))
    assert first == second
    fingerprints = [item["test_fingerprint"] for item in first["classifications"]]
    assert fingerprints == sorted(fingerprints)


def test_rejects_duplicate_record_ids_and_authority_expansion() -> None:
    records = _records()
    with pytest.raises(ValueError, match="duplicate record ids"):
        build_trusted_observation_classification([records[0], deepcopy(records[0])])

    report = build_trusted_observation_classification(records)
    expanded = deepcopy(report)
    expanded["decision_boundary"]["automatic_rerun_allowed"] = True
    with pytest.raises(ValueError, match="authority boundary"):
        validate_classification_report(expanded)


def test_rejects_unbound_or_malformed_provenance() -> None:
    report = build_trusted_observation_classification(_records())
    unbound = deepcopy(report)
    unbound["classifications"][0]["observation_provenance"][0]["source_run_id"] = "unknown-run"
    with pytest.raises(ValueError, match="not bound to source history"):
        validate_classification_report(unbound)

    malformed = deepcopy(report)
    malformed["classifications"][0]["observation_provenance"][0]["test_id"] = "raw-name"
    with pytest.raises(ValueError, match="provenance fields"):
        validate_classification_report(malformed)


def test_rejects_duplicate_provenance_tuple_even_with_consistent_counts() -> None:
    report = build_trusted_observation_classification(_records())
    duplicated = deepcopy(report)
    item = duplicated["classifications"][0]
    item["observation_provenance"].append(deepcopy(item["observation_provenance"][0]))
    item["runs_observed"] += 1
    item["decisive_observation_count"] += 1
    item["failed"] += 1

    with pytest.raises(ValueError, match="duplicate provenance tuples"):
        validate_classification_report(duplicated)


def test_jsonl_reader_and_cli_write_review_first_artifacts(tmp_path: Path, capsys) -> None:
    history_path = tmp_path / "history.jsonl"
    history_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in _records()),
        encoding="utf-8",
    )
    assert len(read_observation_history_records(history_path)) == 2

    out_dir = tmp_path / "classification"
    rc = main(
        [
            "--history-jsonl",
            str(history_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == STATUS

    saved = json.loads((out_dir / CLASSIFICATION_JSON).read_text(encoding="utf-8"))
    markdown = (out_dir / CLASSIFICATION_MD).read_text(encoding="utf-8")
    assert saved["summary"]["flaky"] == 1
    assert saved["summary"]["current_pr_decision_input"] is False
    assert "# Trusted test observation classification" in markdown
    assert "Automatic quarantine allowed: `false`" in markdown
    assert "Automatic rerun allowed: `false`" in markdown
    assert "Current PR decision input: `false`" in markdown


def test_cli_rejects_invalid_history_jsonl(tmp_path: Path, capsys) -> None:
    history_path = tmp_path / "bad-history.jsonl"
    history_path.write_text('{"not":"a history record"}\n', encoding="utf-8")
    rc = main(
        [
            "--history-jsonl",
            str(history_path),
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert rc == 2
    assert "error=" in capsys.readouterr().out


def test_markdown_and_report_keep_every_authority_denied() -> None:
    report = build_trusted_observation_classification(_records())
    markdown = render_classification_markdown(report)
    boundary = report["decision_boundary"]
    assert boundary["advisory_only"] is True
    assert boundary["raw_test_identity_emitted"] is False
    assert boundary["current_pr_decision_input"] is False
    assert boundary["automatic_quarantine_allowed"] is False
    assert boundary["automatic_rerun_allowed"] is False
    assert boundary["current_failure_suppression_allowed"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["patch_application_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False
    assert "Advisory only: `true`" in markdown
    assert "Raw test identity emitted: `false`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
