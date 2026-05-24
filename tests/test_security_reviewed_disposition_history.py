from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import security_reviewed_disposition_history as history


def _merged_pr(head_sha: str = "merged-head") -> list[dict]:
    return [
        {
            "number": 1421,
            "merged_at": "2026-05-24T03:25:40Z",
            "merge_commit_sha": head_sha,
        }
    ]


def _dismissed_alert(*, state: str = "dismissed", comment: str = "Reviewed disposition.") -> dict:
    return {
        "number": 44,
        "state": state,
        "dismissed_by": {"login": "reviewer"},
        "dismissed_at": "2026-05-24T03:20:00Z",
        "dismissed_reason": "false positive",
        "dismissed_comment": comment,
        "tool": {"name": "sdetkit-security-gate"},
        "rule": {"id": "SEC_HIGH_ENTROPY_STRING", "security_severity_level": "warning"},
        "most_recent_instance": {"location": {"path": "src/sdetkit/example.py", "start_line": 22}},
    }


def test_record_sanitizes_reviewed_dismissal_without_authorizing_reuse() -> None:
    secret_comment = "Internal review text must stay outside historical evidence."
    record = history.build_history_record(
        associated_pr_payload=_merged_pr(),
        dismissed_alerts_payload={
            "collection_status": "collected",
            "alerts": [_dismissed_alert(comment=secret_comment)],
        },
        source_run_id="run-1",
        source_head_sha="merged-head",
        recorded_at_utc="2026-05-24T03:30:00Z",
    )

    item = record["reviewed_dispositions"][0]
    serialized = json.dumps(record)
    assert item["state"] == "dismissed"
    assert item["dismissed_by"] == "reviewer"
    assert item["dismissed_reason"] == "false positive"
    assert item["dismissed_comment_present"] is True
    assert "dismissed_comment" not in item
    assert secret_comment not in serialized
    boundary = record["decision_boundary"]
    assert boundary[history.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION] is False
    assert boundary[history.AUTOMATIC_SECURITY_FIX_ALLOWED] is False
    assert boundary[history.AUTOMATIC_DISMISSAL_ALLOWED] is False
    assert boundary[history.AUTOMATION_ALLOWED] is False
    assert boundary[history.MERGE_AUTHORIZED] is False


def test_record_requires_dismissed_state_and_reviewer_provenance() -> None:
    with pytest.raises(ValueError, match="only dismissed"):
        history.build_history_record(
            associated_pr_payload=_merged_pr(),
            dismissed_alerts_payload=[_dismissed_alert(state="open")],
            source_run_id="run-1",
            source_head_sha="merged-head",
        )

    alert = _dismissed_alert()
    alert["dismissed_by"] = {}
    with pytest.raises(ValueError, match="lacks reviewer provenance"):
        history.build_history_record(
            associated_pr_payload=_merged_pr(),
            dismissed_alerts_payload=[alert],
            source_run_id="run-1",
            source_head_sha="merged-head",
        )


def test_record_can_capture_no_dispositions_without_claiming_review() -> None:
    record = history.build_history_record(
        associated_pr_payload=_merged_pr(),
        dismissed_alerts_payload={"collection_status": "collected", "alerts": []},
        source_run_id="run-1",
        source_head_sha="merged-head",
    )
    assert record["reviewed_dispositions"] == []
    assert record["source"]["merged_pr_present"] is True
    assert (
        record["decision_boundary"][history.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION]
        is False
    )


def test_unavailable_collection_carries_no_disposition_claims() -> None:
    record = history.build_history_record(
        associated_pr_payload=_merged_pr(),
        dismissed_alerts_payload={
            "collection_status": "unavailable",
            "collection_reason": "read permission unavailable",
            "alerts": [],
        },
        source_run_id="run-1",
        source_head_sha="merged-head",
    )
    assert record["source"]["collection_status"] == "unavailable"
    assert record["reviewed_dispositions"] == []


def test_prior_history_is_deduplicated_and_rejects_authority_expansion(tmp_path: Path) -> None:
    record = history.build_history_record(
        associated_pr_payload=_merged_pr(),
        dismissed_alerts_payload={"collection_status": "collected", "alerts": []},
        source_run_id="run-1",
        source_head_sha="merged-head",
        recorded_at_utc="2026-05-24T03:30:00Z",
    )
    records, appended = history.merge_history_records([record], record)
    assert appended is False
    assert len(records) == 1

    bad = json.loads(json.dumps(record))
    bad["decision_boundary"][history.AUTOMATIC_DISMISSAL_ALLOWED] = True
    with pytest.raises(ValueError, match="expands security authority"):
        history.merge_history_records([bad], record)


def test_cli_writes_read_only_history_artifacts(tmp_path: Path, capsys) -> None:
    pr_path = tmp_path / "pr.json"
    alerts_path = tmp_path / "alerts.json"
    out_dir = tmp_path / "out"
    pr_path.write_text(json.dumps(_merged_pr()), encoding="utf-8")
    alerts_path.write_text(
        json.dumps({"collection_status": "collected", "alerts": [_dismissed_alert()]}),
        encoding="utf-8",
    )

    rc = history.main(
        [
            "--associated-pr-json",
            str(pr_path),
            "--dismissed-alerts-json",
            str(alerts_path),
            "--source-run-id",
            "run-1",
            "--source-head-sha",
            "merged-head",
            "--recorded-at-utc",
            "2026-05-24T03:30:00Z",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    summary = json.loads((out_dir / history.SUMMARY_JSON).read_text(encoding="utf-8"))
    markdown = (out_dir / history.SUMMARY_MD).read_text(encoding="utf-8")
    assert printed["reviewed_disposition_count"] == 1
    assert summary["latest_record"]["reviewed_disposition_count"] == 1
    assert "Historical disposition authorizes current action: `false`" in markdown
    assert "Automatic dismissal allowed: `false`" in markdown
