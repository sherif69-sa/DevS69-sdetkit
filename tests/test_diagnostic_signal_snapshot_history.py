from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.diagnostic_signal_snapshot_history import (
    HISTORY_JSONL,
    HISTORY_RECORDED,
    RATE_STATUS,
    build_history_record,
    build_history_summary,
    main,
    merge_history_records,
    render_markdown,
    write_history_jsonl,
)


def _snapshot() -> dict:
    return {
        "schema_version": "sdetkit.diagnostic.signal.snapshot.v1",
        "status": "quiet_green_advisory_baseline",
        "snapshot_type": "current_pr_reporting_only",
        "quiet_green_advisory_baseline": True,
        "measurements": {
            "primary_signal_kind": "review_signal",
            "review_signal_present": True,
            "integration_proof_signal_present": False,
            "evidence_graph_node_count": 0,
            "diagnostic_worker_diagnosis_count": 0,
            "runtime_guard_violation_count": 0,
            "current_security_finding_count": 0,
        },
        "kpi_readiness": {
            "advisor_false_positive_rate_status": RATE_STATUS,
            "reviewed_false_positive_count": None,
            "reviewed_observation_count": None,
        },
        "decision_boundary": {
            "reporting_only": True,
            "current_pr_decision_input": False,
            "feeds_repo_memory": False,
            "proof_commands_executed": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _associated_pr(*, merge_sha: str = "merge123", head_sha: str = "head123") -> list[dict]:
    return [
        {
            "number": 1456,
            "merged_at": "2026-05-28T09:33:53Z",
            "merge_commit_sha": merge_sha,
            "head": {"sha": head_sha},
        }
    ]


def _record(run_id: str = "quality-run-1", retention_run_id: str = "history-run-1") -> dict:
    return build_history_record(
        _snapshot(),
        associated_pr_payload=_associated_pr(),
        source_run_id=run_id,
        source_run_conclusion="success",
        source_head_sha="head123",
        retention_run_id=retention_run_id,
        accepted_main_sha="merge123",
        recorded_at_utc="2026-05-28T10:00:00Z",
    )


def test_history_record_retains_snapshot_observation_without_authority_or_rate() -> None:
    record = _record()
    snapshot = record["snapshot"]
    boundary = record["decision_boundary"]

    assert snapshot["status"] == "quiet_green_advisory_baseline"
    assert snapshot["primary_signal_kind"] == "review_signal"
    assert snapshot["review_signal_present"] is True
    assert snapshot["integration_proof_signal_present"] is False
    assert snapshot["advisor_false_positive_rate_status"] == RATE_STATUS
    assert snapshot["reviewed_observation_count"] is None
    assert boundary["current_pr_decision_input"] is False
    assert boundary["feeds_repo_memory"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["historical_snapshot_authorizes_current_action"] is False


@pytest.mark.parametrize(
    "key",
    ["current_pr_decision_input", "feeds_repo_memory", "automation_allowed", "merge_authorized"],
)
def test_history_rejects_snapshot_that_expands_authority(key: str) -> None:
    snapshot = _snapshot()
    snapshot["decision_boundary"][key] = True

    with pytest.raises(ValueError, match="no-authority boundary"):
        build_history_record(
            snapshot,
            associated_pr_payload=_associated_pr(),
            source_run_id="quality-run-1",
            source_run_conclusion="success",
            source_head_sha="head123",
            retention_run_id="history-run-1",
            accepted_main_sha="merge123",
        )


def test_history_rejects_snapshot_that_claims_false_positive_rate() -> None:
    snapshot = _snapshot()
    snapshot["kpi_readiness"]["advisor_false_positive_rate_status"] = "measured"

    with pytest.raises(ValueError, match="without reviewed history"):
        build_history_record(
            snapshot,
            associated_pr_payload=_associated_pr(),
            source_run_id="quality-run-1",
            source_run_conclusion="success",
            source_head_sha="head123",
            retention_run_id="history-run-1",
            accepted_main_sha="merge123",
        )


def test_history_rejects_mismatched_accepted_main_provenance() -> None:
    with pytest.raises(ValueError, match="exactly one merged pull request"):
        build_history_record(
            _snapshot(),
            associated_pr_payload=_associated_pr(merge_sha="other-merge"),
            source_run_id="quality-run-1",
            source_run_conclusion="success",
            source_head_sha="head123",
            retention_run_id="history-run-1",
            accepted_main_sha="merge123",
        )


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("status", "unsupported", "status is not supported"),
        (
            "quiet_green_advisory_baseline",
            False,
            "status and quiet-green flag disagree",
        ),
        (
            "review_signal_present",
            False,
            "review signal presence does not match primary signal kind",
        ),
    ],
)
def test_history_rejects_inconsistent_imported_snapshot_observation(
    key: str, value: object, message: str
) -> None:
    prior = _record()
    prior["snapshot"][key] = value

    with pytest.raises(ValueError, match=message):
        merge_history_records(
            [prior],
            _record(run_id="quality-run-2", retention_run_id="history-run-2"),
        )


def test_history_summary_counts_signals_without_rate(tmp_path: Path) -> None:
    second_snapshot = _snapshot()
    second_snapshot["status"] = "diagnostic_signal_observed"
    second_snapshot["quiet_green_advisory_baseline"] = False
    second_snapshot["measurements"]["primary_signal_kind"] = "integration_proof"
    second_snapshot["measurements"]["review_signal_present"] = False
    second_snapshot["measurements"]["integration_proof_signal_present"] = True
    second = build_history_record(
        second_snapshot,
        associated_pr_payload=_associated_pr(merge_sha="merge456", head_sha="head456"),
        source_run_id="quality-run-2",
        source_run_conclusion="success",
        source_head_sha="head456",
        retention_run_id="history-run-2",
        accepted_main_sha="merge456",
        recorded_at_utc="2026-05-29T10:00:00Z",
    )
    records, appended = merge_history_records([_record()], second)
    history_path = write_history_jsonl(records, out_dir=tmp_path)
    summary = build_history_summary(
        records,
        appended=appended,
        history_path=history_path,
        prior_history_collected=True,
        prior_record_count=1,
    )

    assert summary["status"] == HISTORY_RECORDED
    assert summary["record_count"] == 2
    assert summary["quiet_green_advisory_baseline_record_count"] == 1
    assert summary["review_signal_record_count"] == 1
    assert summary["integration_proof_signal_record_count"] == 1
    assert summary["advisor_false_positive_rate_status"] == RATE_STATUS
    assert summary["reviewed_false_positive_count"] is None

    markdown = render_markdown(summary)
    assert "Advisor false-positive rate status: `requires_reviewed_history`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown


def test_history_cli_deduplicates_source_snapshot_across_retention_reruns_without_mutating_prior_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    pr_path = tmp_path / "associated-pr.json"
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    pr_path.write_text(json.dumps(_associated_pr()), encoding="utf-8")

    first_out = tmp_path / "first"
    first_rc = main(
        [
            "--diagnostic-signal-snapshot",
            str(snapshot_path),
            "--associated-pr-json",
            str(pr_path),
            "--source-run-id",
            "quality-run-1",
            "--source-run-conclusion",
            "success",
            "--source-head-sha",
            "head123",
            "--retention-run-id",
            "history-run-1",
            "--accepted-main-sha",
            "merge123",
            "--recorded-at-utc",
            "2026-05-28T10:00:00Z",
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
    second_out = tmp_path / "second"
    second_rc = main(
        [
            "--diagnostic-signal-snapshot",
            str(snapshot_path),
            "--associated-pr-json",
            str(pr_path),
            "--prior-history-jsonl",
            str(prior_path),
            "--source-run-id",
            "quality-run-1",
            "--source-run-conclusion",
            "success",
            "--source-head-sha",
            "head123",
            "--retention-run-id",
            "history-run-rerun",
            "--accepted-main-sha",
            "merge123",
            "--recorded-at-utc",
            "2026-05-28T10:00:00Z",
            "--out-dir",
            str(second_out),
            "--format",
            "json",
        ]
    )

    assert second_rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["record_count"] == 1
    assert printed["appended"] is False
    assert prior_path.read_text(encoding="utf-8") == prior_before


def test_history_dedup_refreshes_latest_retention_provenance_without_increasing_counts() -> None:
    first = _record(retention_run_id="history-run-1")
    rerun = _record(retention_run_id="history-run-rerun")

    records, appended = merge_history_records([first], rerun)

    assert appended is False
    assert len(records) == 1
    assert records[0]["record_id"] == first["record_id"]
    assert records[0]["source"]["retention_run_id"] == "history-run-rerun"


def test_history_rejects_imported_record_with_forged_identity() -> None:
    record = _record()
    record["record_id"] = "forged-record-id"

    with pytest.raises(ValueError, match="record id does not match retained observation"):
        merge_history_records([record], _record(retention_run_id="history-run-2"))


def test_history_rejects_imported_record_without_read_only_prior_history_boundary() -> None:
    record = _record()
    record["decision_boundary"]["prior_history_is_read_only_input"] = False

    with pytest.raises(ValueError, match="does not preserve read-only prior-history input"):
        merge_history_records([record], _record(retention_run_id="history-run-2"))


def test_history_rejects_imported_record_without_positive_merged_pr_number() -> None:
    record = _record()
    record["source"]["merged_pr_number"] = 0

    with pytest.raises(ValueError, match="lacks merged PR number provenance"):
        merge_history_records([record], _record(retention_run_id="history-run-2"))
