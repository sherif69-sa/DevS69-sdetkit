from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import security_reviewed_disposition_history as history


def _merged_pr(head_sha: str = "merged-head") -> list[dict]:
    return [{"number": 1422, "merged_at": "2026-05-24T03:44:54Z", "merge_commit_sha": head_sha}]


def _changed_files(*paths: str) -> list[dict]:
    return [{"filename": path} for path in paths]


def _dismissed_alert(
    *,
    path: str = "src/sdetkit/example.py",
    state: str = "dismissed",
    comment: str = "Reviewed disposition.",
) -> dict:
    return {
        "number": 44,
        "state": state,
        "dismissed_by": {"login": "reviewer"},
        "dismissed_at": "2026-05-24T03:20:00Z",
        "dismissed_reason": "false positive",
        "dismissed_comment": comment,
        "tool": {"name": "sdetkit-security-gate"},
        "rule": {"id": "SEC_HIGH_ENTROPY_STRING", "security_severity_level": "warning"},
        "most_recent_instance": {"location": {"path": path, "start_line": 22}},
    }


def _build(*, alerts: list[dict], paths: tuple[str, ...] = ("src/sdetkit/example.py",)) -> dict:
    return history.build_history_record(
        associated_pr_payload=_merged_pr(),
        changed_files_payload=_changed_files(*paths),
        dismissed_alerts_payload={"collection_status": "collected", "alerts": alerts},
        source_run_id="run-1",
        source_head_sha="merged-head",
        recorded_at_utc="2026-05-24T03:30:00Z",
    )


def test_record_sanitizes_scoped_reviewed_dismissal_without_authorizing_reuse() -> None:
    secret_comment = "Internal review text must stay outside historical evidence."
    record = _build(alerts=[_dismissed_alert(comment=secret_comment)])
    item = record["reviewed_dispositions"][0]
    serialized = json.dumps(record)
    assert item["state"] == "dismissed"
    assert item[history.PATH_IN_MERGED_PR_CHANGED_FILES] is True
    assert "dismissed_comment" not in item
    assert secret_comment not in serialized
    assert record["source"][history.PR_SCOPE_VERIFICATION] == history.CHANGED_PATHS_PROVEN
    boundary = record["decision_boundary"]
    assert boundary[history.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION] is False
    assert boundary[history.AUTOMATIC_SECURITY_FIX_ALLOWED] is False
    assert boundary[history.AUTOMATIC_DISMISSAL_ALLOWED] is False


def test_pr_filtered_alerts_outside_merged_changed_paths_are_excluded() -> None:
    record = _build(
        alerts=[
            _dismissed_alert(path="src/sdetkit/unrelated_old_file.py"),
            _dismissed_alert(path="tests/test_unrelated_old_file.py"),
        ],
        paths=("src/sdetkit/new_history.py",),
    )
    assert record["reviewed_dispositions"] == []
    source = record["source"]
    assert source[history.ALERTS_RETURNED_BY_PR_FILTER] == 2
    assert source[history.ALERTS_EXCLUDED_OUTSIDE_CHANGED_PATHS] == 2
    assert source[history.PR_SCOPE_VERIFICATION] == history.CHANGED_PATHS_PROVEN


def test_record_accepts_renamed_previous_path_as_pr_scope_provenance() -> None:
    record = history.build_history_record(
        associated_pr_payload=_merged_pr(),
        changed_files_payload=[
            {"filename": "src/sdetkit/new_name.py", "previous_filename": "src/sdetkit/old_name.py"}
        ],
        dismissed_alerts_payload={
            "collection_status": "collected",
            "alerts": [_dismissed_alert(path="src/sdetkit/old_name.py")],
        },
        source_run_id="run-1",
        source_head_sha="merged-head",
    )
    assert len(record["reviewed_dispositions"]) == 1
    assert record["reviewed_dispositions"][0][history.PATH_IN_MERGED_PR_CHANGED_FILES] is True


def test_record_requires_dismissed_state_and_reviewer_provenance_for_scoped_alert() -> None:
    with pytest.raises(ValueError, match="only dismissed"):
        _build(alerts=[_dismissed_alert(state="open")])
    alert = _dismissed_alert()
    alert["dismissed_by"] = {}
    with pytest.raises(ValueError, match="lacks reviewer provenance"):
        _build(alerts=[alert])


def test_merged_record_requires_changed_file_provenance() -> None:
    with pytest.raises(ValueError, match="changed-file provenance"):
        history.build_history_record(
            associated_pr_payload=_merged_pr(),
            changed_files_payload=[],
            dismissed_alerts_payload={"collection_status": "collected", "alerts": []},
            source_run_id="run-1",
            source_head_sha="merged-head",
        )


def test_verified_v2_history_deduplicates_and_rejects_authority_expansion() -> None:
    record = _build(alerts=[])
    records, appended = history.merge_history_records([record], record)
    assert appended is False
    assert len(records) == 1
    bad = json.loads(json.dumps(record))
    bad["decision_boundary"][history.AUTOMATIC_DISMISSAL_ALLOWED] = True
    with pytest.raises(ValueError, match="expands security authority"):
        history.merge_history_records([bad], record)


def test_cli_ignores_unverified_v1_prior_chain_and_writes_v2_artifacts(
    tmp_path: Path, capsys
) -> None:
    pr_path = tmp_path / "pr.json"
    changed_path = tmp_path / "files.json"
    alerts_path = tmp_path / "alerts.json"
    prior_path = tmp_path / "prior.jsonl"
    out_dir = tmp_path / "out"
    pr_path.write_text(json.dumps(_merged_pr()), encoding="utf-8")
    changed_path.write_text(json.dumps(_changed_files("src/sdetkit/example.py")), encoding="utf-8")
    alerts_path.write_text(
        json.dumps({"collection_status": "collected", "alerts": [_dismissed_alert()]}),
        encoding="utf-8",
    )
    prior_path.write_text(
        json.dumps({"schema_version": history.UNVERIFIED_RECORD_SCHEMA_VERSION}) + "\n",
        encoding="utf-8",
    )
    rc = history.main(
        [
            "--associated-pr-json",
            str(pr_path),
            "--changed-files-json",
            str(changed_path),
            "--dismissed-alerts-json",
            str(alerts_path),
            "--prior-history-jsonl",
            str(prior_path),
            "--source-run-id",
            "run-2",
            "--source-head-sha",
            "merged-head",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    summary = json.loads((out_dir / history.SUMMARY_JSON).read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (out_dir / history.HISTORY_JSONL).read_text(encoding="utf-8").splitlines()
    ]
    assert printed[history.IGNORED_UNVERIFIED_PRIOR_RECORD_COUNT] == 1
    assert summary[history.IGNORED_UNVERIFIED_PRIOR_RECORD_COUNT] == 1
    assert summary["record_count"] == 1
    assert records[0]["schema_version"] == history.RECORD_SCHEMA_VERSION
