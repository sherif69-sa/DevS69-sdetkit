from __future__ import annotations

import json
from pathlib import Path

from sdetkit.pr_quality_remediation_refresh import (
    ASSESS_BLOCKED_BY_REVIEW_FIRST,
    ASSESS_BLOCKED_BY_UNKNOWN_FAILURE,
    ASSESS_GREEN_AFTER_SAFE_FIX,
    ASSESS_STALE_WAIT_FOR_REFRESHED_CHECKS,
    build_remediation_refresh,
    main,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_remediation_refresh_marks_green_after_safe_fix_when_refreshed_checks_pass() -> None:
    payload = build_remediation_refresh(
        safe_fix_outcome={
            "attempted": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "new123",
            "previous_head_sha": "old111",
        },
        check_intelligence={
            "current_pr_head_sha": "new123",
            "failed_checks": [],
            "queued_checks": [],
        },
    )

    assert payload["safe_fix_attempted"] is True
    assert payload["safe_fix_committed"] is True
    assert payload["safe_fix_pushed"] is True
    assert payload["safe_fix_commit_sha"] == "new123"
    assert payload["previous_head_sha"] == "old111"
    assert payload["refreshed_head_sha"] == "new123"
    assert payload["proof_after_fix_started"] is True
    assert payload["proof_after_fix_passed"] is True
    assert payload["proof_after_fix_failed"] is False
    assert payload["merge_assessment"] == ASSESS_GREEN_AFTER_SAFE_FIX


def test_remediation_refresh_waits_for_refreshed_queued_checks() -> None:
    payload = build_remediation_refresh(
        safe_fix_outcome={
            "attempted": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "new123",
        },
        check_intelligence={
            "current_pr_head_sha": "new123",
            "failed_checks": [],
            "queued_checks": [{"name": "Fast CI lane (py3.12)", "status": "queued"}],
        },
    )

    assert payload["proof_after_fix_started"] is True
    assert payload["proof_after_fix_passed"] is False
    assert payload["merge_assessment"] == ASSESS_STALE_WAIT_FOR_REFRESHED_CHECKS


def test_remediation_refresh_blocks_review_first_failures() -> None:
    payload = build_remediation_refresh(
        safe_fix_outcome={
            "attempted": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "new123",
        },
        check_intelligence={
            "current_pr_head_sha": "new123",
            "failed_checks": [
                {
                    "name": "ci",
                    "safe_to_auto_fix": False,
                    "diagnosis": {
                        "surface": "release",
                        "title": "Release artifact validation failed",
                    },
                }
            ],
            "queued_checks": [],
        },
    )

    assert payload["remaining_review_first_blockers"] == ["ci"]
    assert payload["proof_after_fix_passed"] is False
    assert payload["merge_assessment"] == ASSESS_BLOCKED_BY_REVIEW_FIRST


def test_remediation_refresh_blocks_unknown_failures_before_review_first_bucket() -> None:
    payload = build_remediation_refresh(
        safe_fix_outcome={
            "attempted": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "new123",
        },
        check_intelligence={
            "current_pr_head_sha": "new123",
            "failed_checks": [
                {
                    "name": "Fast CI lane (py3.11)",
                    "safe_to_auto_fix": False,
                    "diagnosis": {
                        "surface": "unknown",
                        "title": "Unknown failure",
                    },
                }
            ],
            "queued_checks": [],
        },
    )

    assert payload["merge_assessment"] == ASSESS_BLOCKED_BY_UNKNOWN_FAILURE


def test_remediation_refresh_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    safe_fix_outcome = _write_json(
        tmp_path / "safe-fix-outcome.json",
        {
            "attempted": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "new123",
            "previous_head_sha": "old111",
        },
    )
    check_intelligence = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "current_pr_head_sha": "new123",
            "failed_checks": [],
            "queued_checks": [],
        },
    )

    rc = main(
        [
            "--safe-fix-outcome-json",
            str(safe_fix_outcome),
            "--check-intelligence-json",
            str(check_intelligence),
            "--out-dir",
            str(tmp_path / "refresh"),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads((tmp_path / "refresh" / "remediation-refresh.json").read_text())
    markdown = (tmp_path / "refresh" / "remediation-refresh.md").read_text()
    assert payload["merge_assessment"] == ASSESS_GREEN_AFTER_SAFE_FIX
    assert "Remediation refresh" in markdown
    assert "remediation_refresh_json" in stdout
