from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sdetkit import trusted_test_observation_history as history


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _report(
    *,
    run_id: str = "run-1",
    head_sha: str = "a" * 40,
    outcomes: tuple[
        tuple[str, str],
        ...,
    ] = (
        ("suite::test_b", "failed"),
        ("suite::test_a", "passed"),
    ),
) -> dict[str, object]:
    observations = [
        {
            "test_fingerprint": _fingerprint(identity),
            "outcome": outcome,
        }
        for identity, outcome in outcomes
    ]
    counts = {
        outcome: sum(1 for item in observations if item["outcome"] == outcome)
        for outcome in history.ALLOWED_OUTCOMES
    }
    return {
        "schema_version": ("sdetkit.trusted_test_observation_capture.v1"),
        "status": ("trusted_main_observations_captured"),
        "source": {
            "workflow": "CI",
            "job": "Full CI lane",
            "run_id": run_id,
            "head_sha": head_sha,
            "event_name": "push",
            "ref_name": "refs/heads/main",
            "input_kind": "junit_xml",
            "identity_handling": "sha256_digest",
            "input_read_only": True,
            "commands_executed_by_reader": False,
            "trusted_main": True,
        },
        "observations": observations,
        "summary": {
            "observation_count": len(observations),
            **counts,
            "flaky_classification_performed": False,
            "raw_test_identity_emitted": False,
        },
        "decision_boundary": {
            "raw_observation_only": True,
            "raw_test_identity_emitted": False,
            "flaky_classification_performed": False,
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def test_build_record_is_sorted_and_timestamp_independent() -> None:
    report = _report()

    first = history.build_observation_history_record(
        report,
        source_run_id="run-1",
        source_head_sha="a" * 40,
        recorded_at_utc="2026-06-16T01:00:00Z",
    )
    second = history.build_observation_history_record(
        report,
        source_run_id="run-1",
        source_head_sha="a" * 40,
        recorded_at_utc="2026-06-16T02:00:00Z",
    )

    assert first["schema_version"] == ("sdetkit.trusted_test_observation_history.record.v1")
    assert first["record_id"] == second["record_id"]
    assert first["recorded_at_utc"] != second["recorded_at_utc"]
    assert first["observations"] == sorted(
        first["observations"],
        key=lambda item: (
            item["test_fingerprint"],
            item["outcome"],
        ),
    )
    assert first["observation_count"] == 2
    assert first["passed"] == 1
    assert first["failed"] == 1
    assert first["decision_boundary"] == {
        "raw_observation_only": True,
        "flaky_classification_performed": False,
        "current_pr_decision_input": False,
        "automatic_quarantine_allowed": False,
        "automatic_rerun_allowed": False,
        "current_failure_suppression_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda report: report.update({"schema_version": ("unsupported")}),
            "schema",
        ),
        (
            lambda report: report["source"].update({"ref_name": "refs/heads/feature"}),
            "source",
        ),
        (
            lambda report: report["source"].update({"commands_executed_by_reader": True}),
            "execute commands",
        ),
        (
            lambda report: report["summary"].update({"flaky_classification_performed": True}),
            "classified input",
        ),
        (
            lambda report: report["observations"][0].update({"test_id": "raw::identity"}),
            "raw test identity",
        ),
        (
            lambda report: report["summary"].update({"observation_count": 9}),
            "observation count",
        ),
    ],
)
def test_validate_report_rejects_contract_drift(
    mutator,
    message: str,
) -> None:
    report = _report()
    mutator(report)

    with pytest.raises(
        ValueError,
        match=message,
    ):
        history.validate_observation_report(report)


def test_build_record_rejects_explicit_provenance_mismatch() -> None:
    report = _report()

    with pytest.raises(
        ValueError,
        match="source_run_id does not match",
    ):
        history.build_observation_history_record(
            report,
            source_run_id="different-run",
            source_head_sha="a" * 40,
        )

    with pytest.raises(
        ValueError,
        match="source_head_sha does not match",
    ):
        history.build_observation_history_record(
            report,
            source_run_id="run-1",
            source_head_sha="b" * 40,
        )


def test_validate_record_rejects_id_or_authority_drift() -> None:
    record = history.build_observation_history_record(
        _report(),
        source_run_id="run-1",
        source_head_sha="a" * 40,
    )

    bad_id = dict(record)
    bad_id["record_id"] = "wrong"
    with pytest.raises(
        ValueError,
        match="record id",
    ):
        history.validate_observation_history_record(bad_id)

    bad_boundary = json.loads(json.dumps(record))
    bad_boundary["decision_boundary"]["automation_allowed"] = True
    with pytest.raises(
        ValueError,
        match="authority boundary",
    ):
        history.validate_observation_history_record(bad_boundary)


def test_merge_preserves_order_and_deduplicates() -> None:
    first = history.build_observation_history_record(
        _report(),
        source_run_id="run-1",
        source_head_sha="a" * 40,
        recorded_at_utc="2026-06-16T01:00:00Z",
    )
    second = history.build_observation_history_record(
        _report(
            run_id="run-2",
            head_sha="b" * 40,
            outcomes=(
                ("suite::test_a", "failed"),
                ("suite::test_b", "passed"),
            ),
        ),
        source_run_id="run-2",
        source_head_sha="b" * 40,
        recorded_at_utc="2026-06-16T02:00:00Z",
    )

    records, appended = history.merge_observation_history_records(
        [first],
        second,
    )

    assert appended is True
    assert [record["record_id"] for record in records] == [
        first["record_id"],
        second["record_id"],
    ]

    repeated, repeated_appended = history.merge_observation_history_records(
        records,
        second,
    )
    assert repeated_appended is False
    assert repeated == records


def test_summary_aggregates_raw_outcomes_without_classification(
    tmp_path: Path,
) -> None:
    first = history.build_observation_history_record(
        _report(),
        source_run_id="run-1",
        source_head_sha="a" * 40,
    )
    second = history.build_observation_history_record(
        _report(
            run_id="run-2",
            head_sha="b" * 40,
            outcomes=(
                ("suite::test_a", "failed"),
                ("suite::test_b", "passed"),
            ),
        ),
        source_run_id="run-2",
        source_head_sha="b" * 40,
    )

    records, appended = history.merge_observation_history_records(
        [first],
        second,
    )
    summary = history.build_observation_history_summary(
        records,
        appended=appended,
        history_path=tmp_path / history.HISTORY_JSONL,
        prior_history_collected=True,
        prior_record_count=1,
    )

    assert summary["schema_version"] == ("sdetkit.trusted_test_observation_history.v1")
    assert summary["record_count"] == 2
    assert summary["fingerprint_count"] == 2
    assert summary["observation_count"] == 4
    assert summary["passed"] == 2
    assert summary["failed"] == 2
    assert summary["flaky_classification_performed"] is False
    assert summary["current_pr_decision_input"] is False
    assert len(summary["fingerprint_histories"]) == 2

    serialized = json.dumps(summary)
    assert '"classification"' not in serialized
    assert '"test_id"' not in serialized
    assert '"classname"' not in serialized
    assert '"nodeid"' not in serialized


def test_write_history_and_summary_artifacts(
    tmp_path: Path,
) -> None:
    record = history.build_observation_history_record(
        _report(),
        source_run_id="run-1",
        source_head_sha="a" * 40,
    )
    history_path = history.write_observation_history(
        [record],
        out_dir=tmp_path,
    )
    summary = history.build_observation_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    artifacts = history.write_observation_history_summary(
        summary,
        out_dir=tmp_path,
    )

    written = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written == [record]

    saved_summary = json.loads(Path(artifacts["summary_json"]).read_text(encoding="utf-8"))
    markdown = Path(artifacts["summary_markdown"]).read_text(encoding="utf-8")

    assert saved_summary == summary
    assert "# Trusted test observation history" in markdown
    assert "Raw test identity emitted: `false`" in markdown
    assert "Flaky classification performed: `false`" in markdown
    assert "Automatic quarantine allowed: `false`" in markdown
    assert "Current failure suppression allowed: `false`" in markdown


def test_cli_records_initial_and_prior_history(
    tmp_path: Path,
    capsys,
) -> None:
    first_report = tmp_path / "first.json"
    first_report.write_text(
        json.dumps(_report()) + "\n",
        encoding="utf-8",
    )
    first_out = tmp_path / "first-out"

    first_rc = history.main(
        [
            "--observation-report",
            str(first_report),
            "--source-run-id",
            "run-1",
            "--source-head-sha",
            "a" * 40,
            "--out-dir",
            str(first_out),
            "--format",
            "json",
        ]
    )

    assert first_rc == 0
    first_output = json.loads(capsys.readouterr().out)
    assert first_output["record_count"] == 1
    assert first_output["appended"] is True
    assert first_output["flaky_classification_performed"] is False

    second_report = tmp_path / "second.json"
    second_report.write_text(
        json.dumps(
            _report(
                run_id="run-2",
                head_sha="b" * 40,
                outcomes=(
                    ("suite::test_a", "failed"),
                    ("suite::test_b", "passed"),
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    second_out = tmp_path / "second-out"

    second_rc = history.main(
        [
            "--observation-report",
            str(second_report),
            "--source-run-id",
            "run-2",
            "--source-head-sha",
            "b" * 40,
            "--prior-history-jsonl",
            str(first_out / history.HISTORY_JSONL),
            "--out-dir",
            str(second_out),
            "--format",
            "json",
        ]
    )

    assert second_rc == 0
    second_output = json.loads(capsys.readouterr().out)
    assert second_output["record_count"] == 2
    assert second_output["appended"] is True

    history_records = [
        json.loads(line)
        for line in (second_out / history.HISTORY_JSONL).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [item["source_run_id"] for item in history_records] == ["run-1", "run-2"]


def test_cli_rejects_untrusted_observation_source(
    tmp_path: Path,
    capsys,
) -> None:
    report = _report()
    report["source"]["ref_name"] = "refs/heads/feature"
    report_path = tmp_path / "untrusted.json"
    report_path.write_text(
        json.dumps(report) + "\n",
        encoding="utf-8",
    )

    rc = history.main(
        [
            "--observation-report",
            str(report_path),
            "--source-run-id",
            "run-1",
            "--source-head-sha",
            "a" * 40,
            "--out-dir",
            str(tmp_path / "out"),
            "--format",
            "json",
        ]
    )

    assert rc == 2
    assert "error=" in capsys.readouterr().out
