from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import pytest

from sdetkit.trusted_flaky_test_registry_producer import (
    CLASSIFICATION_ADVISORY,
    CLASSIFICATION_EMPTY,
    CLASSIFICATION_NOT_SUPPLIED,
    NO_TEST_OBSERVATIONS,
    PRODUCER_JSON,
    PRODUCER_VETTED_OBSERVATIONS,
    SOURCE_CONNECTED,
    build_producer_report,
    build_trusted_registry_evidence,
    main,
    render_markdown,
)
from sdetkit.trusted_test_observation_classification import (
    SCHEMA_VERSION as CLASSIFICATION_SCHEMA_VERSION,
)
from sdetkit.trusted_test_observation_classification import (
    build_trusted_observation_classification,
)
from sdetkit.trusted_test_observation_history import (
    build_observation_history_record,
)

FINGERPRINT = "a" * 64
HEAD_A = "1" * 40
HEAD_B = "2" * 40


def _capture(
    *,
    run_id: str,
    head_sha: str,
    outcome: str,
) -> dict:
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
            "observation_count": 1,
            "passed": int(outcome == "passed"),
            "failed": int(outcome == "failed"),
            "error": int(outcome == "error"),
            "skipped": int(outcome == "skipped"),
            "flaky_classification_performed": False,
            "raw_test_identity_emitted": False,
        },
        "observations": [
            {
                "test_fingerprint": FINGERPRINT,
                "outcome": outcome,
            }
        ],
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
    outcome: str,
) -> dict:
    return build_observation_history_record(
        _capture(
            run_id=run_id,
            head_sha=head_sha,
            outcome=outcome,
        ),
        source_run_id=run_id,
        source_head_sha=head_sha,
        recorded_at_utc=recorded_at,
    )


def _mixed_classification_report() -> dict:
    return build_trusted_observation_classification(
        [
            _record(
                run_id="full-ci-run-a",
                head_sha=HEAD_A,
                recorded_at="2026-06-16T00:00:00Z",
                outcome="failed",
            ),
            _record(
                run_id="full-ci-run-b",
                head_sha=HEAD_B,
                recorded_at="2026-06-16T01:00:00Z",
                outcome="passed",
            ),
        ]
    )


def test_trusted_producer_emits_explicit_no_observation_registry_without_authority() -> None:
    evidence = build_trusted_registry_evidence(
        source_run_id="producer-run",
        source_head_sha=HEAD_B,
    )
    report = build_producer_report(evidence)

    assert evidence["collection_status"] == "collected"
    assert evidence["status"] == "advisory_registry_collected"
    assert evidence["entries"] == []
    assert evidence["summary"]["entry_count"] == 0
    assert evidence["summary"]["observation_status"] == NO_TEST_OBSERVATIONS
    assert evidence["source"]["kind"] == "trusted_main_artifact"
    assert evidence["source"]["workflow"] == "RepoMemory Profile History"
    assert evidence["source"]["observations_collected"] is False

    handoff = report["classification_handoff"]
    assert handoff["status"] == CLASSIFICATION_NOT_SUPPLIED
    assert handoff["fingerprint_count"] == 0
    assert handoff["forwarded_to_registry"] is False
    assert handoff["current_pr_decision_input"] is False

    boundary = evidence["decision_boundary"]
    assert boundary["automatic_quarantine_allowed"] is False
    assert boundary["automatic_rerun_allowed"] is False
    assert boundary["current_failure_suppression_allowed"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False


def test_valid_empty_dedicated_report_is_validated_and_forwarded() -> None:
    classification = build_trusted_observation_classification([])

    evidence = build_trusted_registry_evidence(
        source_run_id="producer-run",
        source_head_sha=HEAD_B,
        classification_report=classification,
    )
    report = build_producer_report(
        evidence,
        classification_report=classification,
        producer_source_head_sha=HEAD_B,
    )

    assert evidence["entries"] == []
    assert evidence["summary"]["entry_count"] == 0
    handoff = report["classification_handoff"]
    assert handoff["schema_version"] == CLASSIFICATION_SCHEMA_VERSION
    assert handoff["status"] == CLASSIFICATION_EMPTY
    assert handoff["record_count"] == 0
    assert handoff["fingerprint_count"] == 0
    assert handoff["forwarded_to_registry"] is True


def test_valid_mixed_report_forwards_only_flaky_fingerprint_registry_entry() -> None:
    classification = _mixed_classification_report()

    evidence = build_trusted_registry_evidence(
        source_run_id="repo-memory-run",
        source_head_sha=HEAD_B,
        classification_report=classification,
    )
    report = build_producer_report(
        evidence,
        classification_report=classification,
        producer_source_head_sha=HEAD_B,
    )

    assert evidence["summary"]["entry_count"] == 1
    assert evidence["summary"]["observation_count"] == 2
    assert evidence["summary"]["observation_status"] == PRODUCER_VETTED_OBSERVATIONS
    assert evidence["source"]["run_id"] == "repo-memory-run"
    assert evidence["source"]["identity_kind"] == "fingerprint_only"
    assert evidence["source"]["observations_collected"] is True
    entry = evidence["entries"][0]
    assert entry["test_fingerprint"] == FINGERPRINT
    assert "test_id" not in entry
    assert entry["observed_runs"] == 2
    assert entry["observed_passes"] == 1
    assert entry["observed_failures"] == 1
    assert (
        entry["observation_provenance"]
        == classification["classifications"][0]["observation_provenance"]
    )

    handoff = report["classification_handoff"]
    assert handoff["status"] == CLASSIFICATION_ADVISORY
    assert handoff["record_count"] == 2
    assert handoff["fingerprint_count"] == 1
    assert handoff["flaky"] == 1
    assert handoff["stable_failing"] == 0
    assert handoff["stable_passing"] == 0
    assert handoff["insufficient_history"] == 0
    assert handoff["latest_source_run_id"] == "full-ci-run-b"
    assert handoff["latest_source_head_sha"] == HEAD_B
    assert handoff["raw_test_identity_emitted"] is False
    assert handoff["forwarded_to_registry"] is True
    assert handoff["current_pr_decision_input"] is False


def test_full_ci_run_id_may_differ_from_producer_workflow_run_id() -> None:
    classification = _mixed_classification_report()

    evidence = build_trusted_registry_evidence(
        source_run_id="distinct-repo-memory-run",
        source_head_sha=HEAD_B,
        classification_report=classification,
    )
    report = build_producer_report(
        evidence,
        classification_report=classification,
        producer_source_head_sha=HEAD_B,
    )

    assert evidence["source"]["run_id"] == "distinct-repo-memory-run"
    assert report["classification_handoff"]["latest_source_run_id"] == "full-ci-run-b"


def test_trusted_producer_rejects_missing_or_mismatched_provenance() -> None:
    with pytest.raises(ValueError, match="source_run_id is required"):
        build_trusted_registry_evidence(
            source_run_id="",
            source_head_sha=HEAD_B,
        )

    with pytest.raises(ValueError, match="source_head_sha is required"):
        build_trusted_registry_evidence(
            source_run_id="producer-run",
            source_head_sha="",
        )

    with pytest.raises(ValueError, match="must match producer"):
        build_trusted_registry_evidence(
            source_run_id="producer-run",
            source_head_sha="3" * 40,
            classification_report=_mixed_classification_report(),
        )


def _unsupported_schema(report: dict) -> None:
    report["schema_version"] = "unsupported"


def _expand_authority(report: dict) -> None:
    report["decision_boundary"]["automatic_rerun_allowed"] = True


def _unbind_provenance(report: dict) -> None:
    report["classifications"][0]["observation_provenance"][0]["source_run_id"] = "unbound"


def _duplicate_fingerprint(report: dict) -> None:
    report["classifications"].append(deepcopy(report["classifications"][0]))
    report["summary"]["fingerprint_count"] += 1


def _duplicate_provenance_tuple(report: dict) -> None:
    item = report["classifications"][0]
    item["observation_provenance"].append(deepcopy(item["observation_provenance"][0]))
    item["runs_observed"] += 1
    item["decisive_observation_count"] += 1
    item["failed"] += 1


@pytest.mark.parametrize(
    "mutator",
    [
        _unsupported_schema,
        _expand_authority,
        _unbind_provenance,
        _duplicate_fingerprint,
        _duplicate_provenance_tuple,
    ],
)
def test_invalid_dedicated_reports_fail_closed(
    mutator: Callable[[dict], None],
) -> None:
    report = _mixed_classification_report()
    mutator(report)

    with pytest.raises(ValueError):
        build_trusted_registry_evidence(
            source_run_id="producer-run",
            source_head_sha=HEAD_B,
            classification_report=report,
        )


def test_trusted_producer_report_explains_validation_only_boundary() -> None:
    classification = _mixed_classification_report()
    evidence = build_trusted_registry_evidence(
        source_run_id="producer-run",
        source_head_sha=HEAD_B,
        classification_report=classification,
    )
    report = build_producer_report(
        evidence,
        classification_report=classification,
        producer_source_head_sha=HEAD_B,
    )
    markdown = render_markdown(report)

    assert report["status"] == SOURCE_CONNECTED
    assert report["registry"]["observation_count"] == 2
    assert report["registry"]["entry_count"] == 1
    assert report["registry"]["identity_kind"] == "fingerprint_only"
    assert "# Trusted-main flaky-test registry producer" in markdown
    assert "Dedicated classification handoff" in markdown
    assert "Status: `validated_advisory_forwarded_to_registry`" in markdown
    assert "Forwarded to registry: `true`" in markdown
    assert "Current PR decision input: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_producer_report_is_deterministic() -> None:
    classification = _mixed_classification_report()

    first_evidence = build_trusted_registry_evidence(
        source_run_id="producer-run",
        source_head_sha=HEAD_B,
        classification_report=classification,
    )
    first = build_producer_report(
        first_evidence,
        classification_report=classification,
        producer_source_head_sha=HEAD_B,
    )

    second_evidence = build_trusted_registry_evidence(
        source_run_id="producer-run",
        source_head_sha=HEAD_B,
        classification_report=deepcopy(classification),
    )
    second = build_producer_report(
        second_evidence,
        classification_report=deepcopy(classification),
        producer_source_head_sha=HEAD_B,
    )

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(
        second,
        sort_keys=True,
    )


def test_trusted_producer_cli_reads_and_forwards_dedicated_report(
    tmp_path: Path,
    capsys,
) -> None:
    classification_path = tmp_path / "classification.json"
    classification_path.write_text(
        json.dumps(_mixed_classification_report(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "trusted-registry"

    rc = main(
        [
            "--source-run-id",
            "repo-memory-run",
            "--source-head-sha",
            HEAD_B,
            "--classification-report",
            str(classification_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    registry = json.loads(
        (out_dir / "flaky-test-registry-evidence.json").read_text(encoding="utf-8")
    )
    report = json.loads((out_dir / PRODUCER_JSON).read_text(encoding="utf-8"))

    assert printed["status"] == SOURCE_CONNECTED
    assert registry["summary"]["entry_count"] == 1
    assert registry["entries"][0]["test_fingerprint"] == FINGERPRINT
    assert "test_id" not in registry["entries"][0]
    assert report["classification_handoff"]["status"] == CLASSIFICATION_ADVISORY
    assert report["classification_handoff"]["forwarded_to_registry"] is True


def test_trusted_producer_cli_rejects_invalid_json_without_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    classification_path = tmp_path / "classification.json"
    classification_path.write_text(
        "{not-json}\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "trusted-registry"

    rc = main(
        [
            "--source-run-id",
            "repo-memory-run",
            "--source-head-sha",
            HEAD_B,
            "--classification-report",
            str(classification_path),
            "--out-dir",
            str(out_dir),
        ]
    )

    assert rc == 2
    assert "error=" in capsys.readouterr().out
    assert not (out_dir / PRODUCER_JSON).exists()
