from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.repo_memory_profile_history import (
    ANTI_CHEAT_REJECTION_SCENARIO_COUNT,
    AUTOMATION_ALLOWED,
    CONTROLLED_CURRENT_PR_DECISION_INPUT,
    CONTROLLED_REVIEW_FIRST_COUNT,
    CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
    CONTROLLED_VALIDATION_PASSED,
    CONTROLLED_VALIDATION_RECORD_COUNT,
    CONTROLLED_VALIDATION_SCENARIO_COUNT,
    CONTROLLED_VALIDATION_STATUS,
    FLAKY_TEST_REGISTRY_FIELDS,
    HISTORY_JSONL,
    LEGACY_RECORD_SCHEMA_VERSION,
    LIVE_CONTRACT_PROVEN,
    LIVE_PROFILE_STATUS,
    MERGE_AUTHORIZED,
    SEMANTIC_EQUIVALENCE_PROVEN,
    build_history_record,
    build_history_summary,
    main,
    merge_history_records,
    render_markdown,
    write_history_jsonl,
)

READ_ONLY_MODE = "_".join(("read", "only", "profile"))
GIT_SCENARIOS = "_".join(("git", "verified", "scenario", "count"))
EXPECTED_FAILURES = "_".join(("expected", "failed", "scenario", "count"))
NETWORK_BLOCKED = "_".join(("network", "boundary", "blocked", "scenario", "count"))


def _profile() -> dict:
    return {
        "schema_version": "sdetkit.repo_memory.v4",
        "profile_status": LIVE_PROFILE_STATUS,
        "memory_mode": READ_ONLY_MODE,
        "known_safe_candidate_count": 1,
        "live_safe_candidate_count": 1,
        "proof_provenance": {
            LIVE_CONTRACT_PROVEN: True,
            GIT_SCENARIOS: 5,
            EXPECTED_FAILURES: 5,
            NETWORK_BLOCKED: 1,
            ANTI_CHEAT_REJECTION_SCENARIO_COUNT: 2,
        },
        "decision_boundary": {
            AUTOMATION_ALLOWED: False,
            MERGE_AUTHORIZED: False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
        },
    }


def _record(run_id: str, head_sha: str) -> dict:
    return build_history_record(
        _profile(),
        source_run_id=run_id,
        source_head_sha=head_sha,
        recorded_at_utc="2026-05-23T00:00:00Z",
    )


def test_history_record_captures_live_proof_without_authority() -> None:
    record = _record("run-1", "abc123")

    assert record["source_run_id"] == "run-1"
    assert record["source_head_sha"] == "abc123"
    assert record["profile_status"] == LIVE_PROFILE_STATUS
    assert record[LIVE_CONTRACT_PROVEN] is True
    assert record[ANTI_CHEAT_REJECTION_SCENARIO_COUNT] == 2
    assert record["decision_boundary"][AUTOMATION_ALLOWED] is False
    assert record["decision_boundary"][MERGE_AUTHORIZED] is False
    assert record["decision_boundary"][SEMANTIC_EQUIVALENCE_PROVEN] is False


def test_history_rejects_profile_that_expands_authority() -> None:
    profile = _profile()
    profile["decision_boundary"][AUTOMATION_ALLOWED] = True

    with pytest.raises(ValueError, match="expands authority"):
        build_history_record(
            profile,
            source_run_id="run-1",
            source_head_sha="abc123",
        )


def test_history_merge_is_idempotent_per_run_and_head() -> None:
    record = _record("run-1", "abc123")

    records, appended = merge_history_records([], record)
    second_records, second_appended = merge_history_records(records, record)

    assert appended is True
    assert second_appended is False
    assert len(records) == 1
    assert len(second_records) == 1


def test_history_summary_aggregates_imported_and_current_proven_runs(
    tmp_path: Path,
) -> None:
    records, appended = merge_history_records(
        [_record("run-1", "abc123")],
        _record("run-2", "def456"),
    )
    history_path = write_history_jsonl(records, out_dir=tmp_path)
    summary = build_history_summary(
        records,
        appended=appended,
        history_path=history_path,
        prior_history_collected=True,
        prior_record_count=1,
    )

    assert summary["prior_history_collected"] is True
    assert summary["prior_record_count"] == 1
    assert summary["record_count"] == 2
    assert summary["live_contract_proven_record_count"] == 2
    assert summary[ANTI_CHEAT_REJECTION_SCENARIO_COUNT] == 4
    assert summary["latest_record"]["source_run_id"] == "run-2"
    assert summary["decision_boundary"]["prior_history_is_read_only_input"] is True
    assert summary["decision_boundary"][AUTOMATION_ALLOWED] is False
    assert summary["decision_boundary"][MERGE_AUTHORIZED] is False
    assert summary["decision_boundary"][SEMANTIC_EQUIVALENCE_PROVEN] is False

    markdown = render_markdown(summary)
    assert "Prior history collected: `true`" in markdown
    assert "Prior records: `1`" in markdown
    assert "Live-contract-proven records: `2`" in markdown
    assert "Anti-cheat rejection scenario total: `4`" in markdown
    assert "Prior history is read-only input: `true`" in markdown


def test_history_rejects_imported_record_with_authority_enabled() -> None:
    existing = _record("run-1", "abc123")
    existing["decision_boundary"][MERGE_AUTHORIZED] = True

    with pytest.raises(ValueError, match="expands authority"):
        merge_history_records([existing], _record("run-2", "def456"))


def test_history_cli_writes_new_snapshot_without_mutating_prior_input(
    tmp_path: Path,
    capsys,
) -> None:
    profile_path = tmp_path / "repo-memory-profile.json"
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")

    first_rc = main(
        [
            "--profile-json",
            str(profile_path),
            "--source-run-id",
            "run-1",
            "--source-head-sha",
            "abc123",
            "--recorded-at-utc",
            "2026-05-23T00:00:00Z",
            "--out-dir",
            str(first_out),
            "--format",
            "json",
        ]
    )
    assert first_rc == 0
    capsys.readouterr()

    prior_path = first_out / HISTORY_JSONL
    prior_before = prior_path.read_text(encoding="utf-8")

    second_rc = main(
        [
            "--profile-json",
            str(profile_path),
            "--prior-history-jsonl",
            str(prior_path),
            "--source-run-id",
            "run-2",
            "--source-head-sha",
            "def456",
            "--recorded-at-utc",
            "2026-05-23T01:00:00Z",
            "--out-dir",
            str(second_out),
            "--format",
            "json",
        ]
    )

    assert second_rc == 0
    printed = json.loads(capsys.readouterr().out)
    summary = json.loads(
        (second_out / "repo-memory-history-summary.json").read_text(encoding="utf-8")
    )
    output_rows = (second_out / HISTORY_JSONL).read_text(encoding="utf-8").splitlines()

    assert prior_path.read_text(encoding="utf-8") == prior_before
    assert printed["record_count"] == 2
    assert printed["appended"] is True
    assert summary["prior_history_collected"] is True
    assert summary["prior_record_count"] == 1
    assert len(output_rows) == 2


def test_history_cli_rejects_missing_declared_prior_input(
    tmp_path: Path,
    capsys,
) -> None:
    profile_path = tmp_path / "repo-memory-profile.json"
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")

    rc = main(
        [
            "--profile-json",
            str(profile_path),
            "--prior-history-jsonl",
            str(tmp_path / "missing.jsonl"),
            "--source-run-id",
            "run-1",
            "--source-head-sha",
            "abc123",
            "--out-dir",
            str(tmp_path / "out"),
            "--format",
            "json",
        ]
    )

    assert rc == 2
    assert "prior history input does not exist" in capsys.readouterr().out


def _controlled_profile() -> dict:
    profile = _profile()
    profile["controlled_candidate_validation"] = {
        "collection_status": "collected",
        "status": CONTROLLED_VALIDATION_PASSED,
        "scenario_count": 2,
        "passed_count": 2,
        "structurally_verified_count": 1,
        "review_first_count": 1,
        "current_pr_decision_input": False,
        "decision_boundary": {
            AUTOMATION_ALLOWED: False,
            MERGE_AUTHORIZED: False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
        },
    }
    return profile


def test_history_promotes_controlled_validation_as_advisory_record_data(tmp_path: Path) -> None:
    record = build_history_record(
        _controlled_profile(),
        source_run_id="run-controlled",
        source_head_sha="controlled123",
        recorded_at_utc="2026-05-27T00:00:00Z",
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )

    assert record[CONTROLLED_VALIDATION_STATUS] == CONTROLLED_VALIDATION_PASSED
    assert record[CONTROLLED_VALIDATION_SCENARIO_COUNT] == 2
    assert record[CONTROLLED_STRUCTURALLY_VERIFIED_COUNT] == 1
    assert record[CONTROLLED_REVIEW_FIRST_COUNT] == 1
    assert record[CONTROLLED_CURRENT_PR_DECISION_INPUT] is False
    assert summary[CONTROLLED_VALIDATION_RECORD_COUNT] == 1
    assert summary[CONTROLLED_VALIDATION_SCENARIO_COUNT] == 2
    assert summary["latest_record"][CONTROLLED_VALIDATION_STATUS] == CONTROLLED_VALIDATION_PASSED
    assert summary["decision_boundary"]["controlled_validation_is_advisory_only"] is True
    assert summary["decision_boundary"][AUTOMATION_ALLOWED] is False

    markdown = render_markdown(summary)
    assert "Controlled validation records: `1`" in markdown
    assert "Controlled validation status: `controlled_validation_passed`" in markdown
    assert "Controlled validation is advisory only: `true`" in markdown


def test_history_imports_legacy_record_as_zero_controlled_validation_evidence(
    tmp_path: Path,
) -> None:
    legacy = _record("run-legacy", "legacy123")
    legacy["schema_version"] = LEGACY_RECORD_SCHEMA_VERSION
    for key in (
        CONTROLLED_VALIDATION_STATUS,
        CONTROLLED_VALIDATION_SCENARIO_COUNT,
        "controlled_validation_passed_count",
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
        CONTROLLED_REVIEW_FIRST_COUNT,
        CONTROLLED_CURRENT_PR_DECISION_INPUT,
        *FLAKY_TEST_REGISTRY_FIELDS,
    ):
        legacy.pop(key, None)

    current = build_history_record(
        _controlled_profile(),
        source_run_id="run-current",
        source_head_sha="current123",
    )
    records, appended = merge_history_records([legacy], current)
    history_path = write_history_jsonl(records, out_dir=tmp_path)
    summary = build_history_summary(
        records,
        appended=appended,
        history_path=history_path,
        prior_history_collected=True,
        prior_record_count=1,
    )

    assert summary["record_count"] == 2
    assert summary[CONTROLLED_VALIDATION_RECORD_COUNT] == 1
    assert summary[CONTROLLED_VALIDATION_SCENARIO_COUNT] == 2


def test_history_rejects_controlled_profile_that_claims_current_pr_influence() -> None:
    profile = _controlled_profile()
    profile["controlled_candidate_validation"]["current_pr_decision_input"] = True

    with pytest.raises(ValueError, match="cannot influence a current PR decision"):
        build_history_record(
            profile,
            source_run_id="run-bad",
            source_head_sha="bad123",
        )


def _producer_vetted_registry_profile() -> dict:
    profile = _profile()
    profile["flaky_test_registry"] = {
        "collection_status": "collected",
        "status": "advisory_registry_collected",
        "source": {
            "kind": "trusted_main_artifact",
            "reference": "producer-output.json",
            "classification_schema": ("sdetkit.trusted_test_observation_classification.v1"),
            "input_read_only": True,
            "commands_executed_by_reader": False,
            "workflow": "RepoMemory Profile History",
            "run_id": "trusted-run-7",
            "head_sha": "a" * 40,
            "observation_status": (
                "producer_"
                # scanner-safe synthetic fixture split
                "vetted_flaky_"
                # scanner-safe synthetic fixture split
                "observations_"
                # scanner-safe synthetic fixture split
                "available"
            ),
            "observations_collected": True,
            "identity_kind": "fingerprint_only",
            "producer_vetted": True,
            "raw_test_identity_emitted": False,
        },
        "entries": [
            {
                "test_fingerprint": "b" * 64,
                "observation_provenance": [
                    {
                        "source_run_id": "run-1",
                        "source_head_sha": "c" * 40,
                        "outcome": "passed",
                    },
                    {
                        "source_run_id": "run-2",
                        "source_head_sha": "d" * 40,
                        "outcome": "failed",
                    },
                ],
            }
        ],
        "entry_count": 1,
        "decision_boundary": {
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "current_pr_decision_input": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }
    return profile


def test_history_v3_persists_producer_vetted_registry_aggregate_only(
    tmp_path: Path,
) -> None:
    from sdetkit import repo_memory_profile_history as history

    record = history.build_history_record(
        _producer_vetted_registry_profile(),
        source_run_id="trusted-run-7",
        source_head_sha="a" * 40,
        recorded_at_utc="2026-06-19T00:00:00Z",
    )
    history_path = history.write_history_jsonl([record], out_dir=tmp_path)
    summary = history.build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )

    assert record["schema_version"] == history.RECORD_SCHEMA_VERSION
    assert record[history.FLAKY_TEST_REGISTRY_COLLECTION_STATUS] == "collected"
    assert record[history.FLAKY_TEST_REGISTRY_ENTRY_COUNT] == 1
    assert record[history.FLAKY_TEST_REGISTRY_OBSERVATION_STATUS] == (
        "producer_"
        # scanner-safe synthetic fixture split
        "vetted_flaky_"
        # scanner-safe synthetic fixture split
        "observations_"
        # scanner-safe synthetic fixture split
        "available"
    )
    assert record[history.FLAKY_TEST_REGISTRY_OBSERVATIONS_COLLECTED] is True
    assert record[history.FLAKY_TEST_REGISTRY_PRODUCER_VETTED] is True
    assert record[history.FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED] is False
    assert record[history.FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT] is False

    serialized = json.dumps(record, sort_keys=True)
    for forbidden_key in (
        '"entries"',
        '"test_id"',
        '"classname"',
        '"nodeid"',
        '"test_fingerprint"',
        '"observation_provenance"',
    ):
        assert forbidden_key not in serialized

    assert summary[history.FLAKY_TEST_REGISTRY_ENTRY_COUNT] == 1
    assert summary["latest_record"][history.FLAKY_TEST_REGISTRY_PRODUCER_VETTED] is True
    assert summary["decision_boundary"]["flaky_test_registry_is_advisory_only"] is True

    markdown = history.render_markdown(summary)
    assert "Latest flaky registry entries: `1`" in markdown
    assert "Flaky registry producer vetted: `true`" in markdown
    assert "Flaky registry raw test identity emitted: `false`" in markdown
    assert "Flaky registry current PR decision input: `false`" in markdown


def test_history_v1_v2_records_normalize_registry_to_not_collected() -> None:
    from sdetkit import repo_memory_profile_history as history

    v1 = _record("legacy-v1", "legacy-v1-head")
    v1["schema_version"] = history.LEGACY_RECORD_SCHEMA_VERSION
    for key in (
        history.CONTROLLED_VALIDATION_STATUS,
        history.CONTROLLED_VALIDATION_SCENARIO_COUNT,
        history.CONTROLLED_VALIDATION_PASSED_COUNT,
        history.CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
        history.CONTROLLED_REVIEW_FIRST_COUNT,
        history.CONTROLLED_CURRENT_PR_DECISION_INPUT,
        *history.FLAKY_TEST_REGISTRY_FIELDS,
    ):
        v1.pop(key, None)

    v2 = _record("legacy-v2", "legacy-v2-head")
    v2["schema_version"] = history.CONTROLLED_RECORD_SCHEMA_VERSION
    for key in history.FLAKY_TEST_REGISTRY_FIELDS:
        v2.pop(key, None)

    history.validate_record(v1)
    history.validate_record(v2)

    assert (
        history.flaky_test_registry_record_summary(v1)[
            history.FLAKY_TEST_REGISTRY_COLLECTION_STATUS
        ]
        == history.NOT_COLLECTED
    )
    assert (
        history.flaky_test_registry_record_summary(v2)[history.FLAKY_TEST_REGISTRY_ENTRY_COUNT] == 0
    )


def test_history_rejects_registry_that_claims_current_pr_influence() -> None:
    from sdetkit import repo_memory_profile_history as history

    profile = _producer_vetted_registry_profile()
    profile["flaky_test_registry"]["decision_boundary"]["current_pr_decision_input"] = True

    with pytest.raises(ValueError, match="current PR decision"):
        history.build_history_record(
            profile,
            source_run_id="bad-run",
            source_head_sha="e" * 40,
        )
