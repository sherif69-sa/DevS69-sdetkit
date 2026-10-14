from __future__ import annotations

import json
from pathlib import Path

from sdetkit import merge_readiness


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_required_contexts_green_while_optional_skips_remain_nonblocking(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "required_contexts": ["CI", "Security"],
            "check_runs": [
                {
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": "head-1",
                },
                {
                    "name": "Security",
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": "head-1",
                },
                {
                    "name": "Optional docs preview",
                    "status": "completed",
                    "conclusion": "skipped",
                    "required": False,
                    "head_sha": "head-1",
                },
            ],
        },
    )

    report = merge_readiness.build_merge_readiness(
        checks_json=checks,
        current_head_sha="head-1",
    )

    assert report["schema_version"] == merge_readiness.MERGE_READINESS_SCHEMA_VERSION
    assert report["status"] == "green"
    assert report["observed_required_checks_green"] is True
    assert [item["name"] for item in report["required_checks"]] == ["CI", "Security"]
    assert report["counts"]["required"]["green"] == 2
    assert report["counts"]["optional"]["skipped"] == 1
    assert report["merge_authorized"] is False
    assert report["automation_allowed"] is False


def test_failed_required_check_has_priority_over_action_required_and_pending(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "failure",
                    "required": True,
                    "url": "https://example.test/ci",
                },
                {
                    "name": "Protected deploy proof",
                    "status": "completed",
                    "conclusion": "action_required",
                    "required": True,
                },
                {
                    "name": "PR Quality",
                    "status": "queued",
                    "conclusion": "",
                    "required": True,
                },
            ]
        },
    )

    report = merge_readiness.build_merge_readiness(checks_json=checks)

    assert report["status"] == "failed"
    assert report["counts"]["required"]["failed"] == 1
    assert report["counts"]["required"]["action_required"] == 1
    assert report["counts"]["required"]["pending"] == 1
    assert report["next_owner_action"] == {
        "check": "CI",
        "action": (
            "Open the failed required check, fix the first real failing contract, "
            "then refresh this report on the current head."
        ),
        "url": "https://example.test/ci",
    }


def test_action_required_check_names_the_approval_action(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "workflow_runs": [
                {
                    "name": "Protected environment proof",
                    "status": "completed",
                    "conclusion": "action_required",
                    "required": True,
                    "url": "https://example.test/runs/42",
                }
            ]
        },
    )

    report = merge_readiness.build_merge_readiness(checks_json=checks)

    assert report["status"] == "action_required"
    assert report["required_checks"][0]["state"] == "action_required"
    assert "approval or start action" in report["next_owner_action"]["action"]
    assert report["next_owner_action"]["url"] == "https://example.test/runs/42"


def test_stale_required_success_is_action_required_not_green(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "required": True,
                    "head_sha": "old-head",
                    "url": "https://example.test/ci",
                }
            ]
        },
    )

    report = merge_readiness.build_merge_readiness(
        checks_json=checks,
        current_head_sha="new-head",
    )

    assert report["status"] == "action_required"
    assert report["required_checks"][0]["stale"] is True
    assert report["required_checks"][0]["state"] == "action_required"
    assert "current head" in report["next_owner_action"]["action"]


def test_required_skipped_check_requests_trigger_review(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "checks": [
                {
                    "name": "Required release proof",
                    "status": "completed",
                    "conclusion": "skipped",
                    "required": True,
                }
            ]
        },
    )

    report = merge_readiness.build_merge_readiness(checks_json=checks)

    assert report["status"] == "action_required"
    assert report["required_checks"][0]["state"] == "skipped"
    assert "trigger or condition" in report["next_owner_action"]["action"]


def test_missing_required_context_is_pending_evidence(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "required_contexts": ["CI", "Security"],
            "check_runs": [
                {
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
        },
    )

    report = merge_readiness.build_merge_readiness(checks_json=checks)

    assert report["status"] == "pending"
    assert report["missing_required_contexts"] == ["Security"]
    missing = next(item for item in report["required_checks"] if item["name"] == "Security")
    assert missing["missing_required_context"] is True
    assert missing["state"] == "pending"
    assert "Provide or start" in report["next_owner_action"]["action"]


def test_absent_required_metadata_remains_unknown(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
    )

    report = merge_readiness.build_merge_readiness(checks_json=checks)

    assert report["status"] == "unknown"
    assert report["required_checks"] == []
    assert report["observed_required_checks_green"] is False
    assert "required-context metadata" in report["next_owner_action"]["action"]
    assert report["merge_authorized"] is False


def test_cli_writes_deterministic_json_and_markdown_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "CI",
                    "status": "queued",
                    "conclusion": "",
                    "required": True,
                }
            ]
        },
    )
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"

    assert (
        merge_readiness.main(
            [
                "--checks-json",
                str(checks),
                "--current-head-sha",
                "head-1",
                "--out-dir",
                str(first_out),
            ]
        )
        == 0
    )
    first_paths = json.loads(capsys.readouterr().out)
    assert first_paths["merge_readiness"] == (first_out / "merge-readiness.json").as_posix()

    assert (
        merge_readiness.main(
            [
                "--checks-json",
                str(checks),
                "--current-head-sha",
                "head-1",
                "--out-dir",
                str(second_out),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (first_out / "merge-readiness.json").read_bytes() == (
        second_out / "merge-readiness.json"
    ).read_bytes()
    assert (first_out / "merge-readiness.md").read_bytes() == (
        second_out / "merge-readiness.md"
    ).read_bytes()

    markdown = (first_out / "merge-readiness.md").read_text(encoding="utf-8")
    assert "Status: `pending`" in markdown
    assert "## Next owner action" in markdown
    assert "Merge authorized: `false`" in markdown
