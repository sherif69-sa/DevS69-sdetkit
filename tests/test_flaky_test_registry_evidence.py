from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.flaky_test_registry_evidence import (
    STATUS,
    TRUSTED_SOURCE_IDENTITY_KIND,
    build_flaky_test_registry_evidence,
    build_producer_vetted_fingerprint_registry_evidence,
    main,
    render_markdown,
)
from sdetkit.trusted_test_observation_classification import (
    SCHEMA_VERSION as TRUSTED_CLASSIFICATION_SCHEMA_VERSION,
)
from sdetkit.trusted_test_observation_classification import (
    build_trusted_observation_classification,
)
from sdetkit.trusted_test_observation_history import (
    build_observation_history_record,
)


def _classification_report() -> dict:
    return {
        "schema_version": "sdetkit.intelligence.flake.v1",
        "tests": [
            {
                "test_id": "tests/test_service.py::test_retry_path",
                "classification": "flaky",
                "signal": "nondeterministic-rerun",
                "next_step": "Quarantine test and capture deterministic evidence.",
                "runs": 3,
                "failures": 1,
                "passes": 2,
                "fingerprint": "abcd1234",
            },
            {
                "test_id": "tests/test_service.py::test_stable_failure",
                "classification": "stable-failing",
                "runs": 2,
                "failures": 2,
                "passes": 0,
                "fingerprint": "stable0001",
            },
        ],
        "summary": {
            "flaky": 1,
            "stable_failing": 1,
            "stable_passing": 0,
        },
    }


TRUSTED_FLAKY_FINGERPRINT = "f" * 64
TRUSTED_STABLE_FINGERPRINT = "e" * 64
TRUSTED_HEAD_A = "1" * 40
TRUSTED_HEAD_B = "2" * 40


def _trusted_capture(
    *,
    run_id: str,
    head_sha: str,
    flaky_outcome: str,
) -> dict:
    observations = [
        {
            "test_fingerprint": TRUSTED_FLAKY_FINGERPRINT,
            "outcome": flaky_outcome,
        },
        {
            "test_fingerprint": TRUSTED_STABLE_FINGERPRINT,
            "outcome": "passed",
        },
    ]
    counts = {
        "passed": sum(item["outcome"] == "passed" for item in observations),
        "failed": sum(item["outcome"] == "failed" for item in observations),
        "error": 0,
        "skipped": 0,
    }
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


def _trusted_record(
    *,
    run_id: str,
    head_sha: str,
    recorded_at: str,
    flaky_outcome: str,
) -> dict:
    return build_observation_history_record(
        _trusted_capture(
            run_id=run_id,
            head_sha=head_sha,
            flaky_outcome=flaky_outcome,
        ),
        source_run_id=run_id,
        source_head_sha=head_sha,
        recorded_at_utc=recorded_at,
    )


def _trusted_classification_report() -> dict:
    return build_trusted_observation_classification(
        [
            _trusted_record(
                run_id="full-ci-a",
                head_sha=TRUSTED_HEAD_A,
                recorded_at="2026-06-16T00:00:00Z",
                flaky_outcome="failed",
            ),
            _trusted_record(
                run_id="full-ci-b",
                head_sha=TRUSTED_HEAD_B,
                recorded_at="2026-06-16T01:00:00Z",
                flaky_outcome="passed",
            ),
        ]
    )


def test_flaky_test_registry_normalizes_flake_evidence_without_authority() -> None:
    evidence = build_flaky_test_registry_evidence(
        classification_report=_classification_report(),
        source_kind="operator_review_input",
        source_reference="local-proof",
    )

    assert evidence["status"] == STATUS
    assert evidence["summary"]["entry_count"] == 1
    entry = evidence["entries"][0]
    assert entry["test_id"] == "tests/test_service.py::test_retry_path"
    assert entry["decision"] == "instability_context_only"
    assert "next_step" not in entry
    assert entry["automatic_quarantine_allowed"] is False
    assert entry["current_failure_suppression_allowed"] is False

    boundary = evidence["decision_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_producer_vetted_registry_maps_only_flaky_fingerprints() -> None:
    classification = _trusted_classification_report()
    evidence = build_producer_vetted_fingerprint_registry_evidence(
        classification_report=classification,
        source_reference="trusted-producer",
    )

    assert evidence["status"] == STATUS
    assert evidence["source"]["kind"] == "trusted_main_artifact"
    assert evidence["source"]["identity_kind"] == TRUSTED_SOURCE_IDENTITY_KIND
    assert evidence["source"]["classification_schema"] == TRUSTED_CLASSIFICATION_SCHEMA_VERSION
    assert evidence["source"]["producer_vetted"] is True
    assert evidence["source"]["raw_test_identity_emitted"] is False
    assert evidence["summary"]["classification_fingerprint_count"] == 2
    assert evidence["summary"]["entry_count"] == 1

    entry = evidence["entries"][0]
    assert entry["test_fingerprint"] == TRUSTED_FLAKY_FINGERPRINT
    assert entry["classification"] == "flaky"
    assert entry["observed_runs"] == 2
    assert entry["decisive_observation_count"] == 2
    assert entry["observed_passes"] == 1
    assert entry["observed_failures"] == 1
    assert entry["observed_errors"] == 0
    assert entry["observed_skipped"] == 0
    assert (
        entry["observation_provenance"]
        == classification["classifications"][1]["observation_provenance"]
    )
    assert "test_id" not in entry
    assert "fingerprint" not in entry
    assert entry["current_pr_decision_input"] is False
    assert entry["automatic_quarantine_allowed"] is False
    assert entry["automatic_rerun_allowed"] is False
    assert entry["current_failure_suppression_allowed"] is False
    assert entry["automation_allowed"] is False
    assert entry["patch_application_allowed"] is False
    assert entry["merge_authorized"] is False
    assert entry["semantic_equivalence_proven"] is False


def test_producer_vetted_registry_is_deterministic_and_separate_from_legacy() -> None:
    classification = _trusted_classification_report()
    first = build_producer_vetted_fingerprint_registry_evidence(
        classification_report=classification,
        source_reference="trusted-producer",
    )
    second = build_producer_vetted_fingerprint_registry_evidence(
        classification_report=json.loads(json.dumps(classification)),
        source_reference="trusted-producer",
    )

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    with pytest.raises(ValueError, match="unsupported flaky-test classification report schema"):
        build_flaky_test_registry_evidence(
            classification_report=classification,
            source_kind="trusted_main_artifact",
            source_reference="trusted-producer",
        )


def test_flaky_test_registry_rejects_unproven_flaky_entry() -> None:
    report = _classification_report()
    report["tests"][0]["passes"] = 0

    try:
        build_flaky_test_registry_evidence(
            classification_report=report,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )
    except ValueError as exc:
        assert "mixed pass/fail observations" in str(exc)
    else:
        raise AssertionError("expected invalid flaky evidence to be rejected")


def test_flaky_test_registry_markdown_exposes_review_first_boundary() -> None:
    markdown = render_markdown(
        build_flaky_test_registry_evidence(
            classification_report=_classification_report(),
            source_kind="operator_review_input",
            source_reference="local-proof",
        )
    )

    assert "# Flaky-test registry evidence" in markdown
    assert "decision=`instability_context_only`" in markdown
    assert "Automatic quarantine allowed: `false`" in markdown
    assert "Current failure suppression allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown


def test_flaky_test_registry_cli_writes_deterministic_artifacts(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "classification.json"
    out_dir = tmp_path / "registry"
    input_path.write_text(json.dumps(_classification_report()), encoding="utf-8")

    rc = main(
        [
            "--classification-report",
            str(input_path),
            "--source-kind",
            "operator_review_input",
            "--source-reference",
            "local-proof",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "flaky-test-registry-evidence.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "flaky-test-registry-evidence.md").read_text(encoding="utf-8")

    assert printed["status"] == "written"
    assert saved["status"] == STATUS
    assert saved["source"]["input_read_only"] is True
    assert "Automation allowed: `false`" in markdown


def test_flaky_test_registry_rejects_missing_source_reference_and_malformed_report() -> None:
    with pytest.raises(ValueError, match="source reference is required"):
        build_flaky_test_registry_evidence(
            classification_report=_classification_report(),
            source_kind="trusted_main_artifact",
            source_reference="",
        )

    malformed = {
        "schema_version": "sdetkit.intelligence.flake.v1",
        "tests": "not-a-list",
    }
    with pytest.raises(ValueError, match="tests array"):
        build_flaky_test_registry_evidence(
            classification_report=malformed,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )


def test_flaky_test_registry_rejects_non_object_or_unknown_classification_entry() -> None:
    malformed = _classification_report()
    malformed["tests"] = ["not-an-object"]

    with pytest.raises(ValueError, match="non-object entry"):
        build_flaky_test_registry_evidence(
            classification_report=malformed,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )

    unknown = _classification_report()
    unknown["tests"][0]["classification"] = "maybe-flaky"

    with pytest.raises(ValueError, match="unsupported flaky-test classification"):
        build_flaky_test_registry_evidence(
            classification_report=unknown,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )
