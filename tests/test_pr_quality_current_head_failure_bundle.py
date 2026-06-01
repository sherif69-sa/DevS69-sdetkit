from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence
from sdetkit.pr_quality_action_report import main, write_comment_body


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_pr_quality_action_report_writes_optional_current_head_failure_bundle(tmp_path):
    action_report_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "review_required",
            "review_first": True,
            "safe_fix_available": False,
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "review-first failure",
            },
            "primary_blocker": {
                "code": "TEST_FAILURE",
                "title": "Test failure",
                "review_first": True,
                "impact": "human review required before merge",
            },
            "recommended_actions": ["Review the failing test before merge."],
            "proof_commands": ["python -m pytest -q tests/test_contract.py -o addopts="],
        },
    )
    check_intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 3,
            "head_sha": "head-from-intelligence",
            "base_sha": "base-from-intelligence",
            "failed_checks": [
                {
                    "name": "Full CI lane",
                    "review_first": True,
                    "safe_to_auto_fix": False,
                    "first_failure": {
                        "line": "FAILED tests/test_contract.py::test_contract",
                        "line_number": 17,
                        "tool": "pytest",
                        "kind": "test_failure",
                    },
                    check_intelligence.FAILED_STEP_EVIDENCE_KEY: {
                        "status": "found",
                        "command": "python -m pytest -q tests/test_contract.py -o addopts=",
                        "source": "github_actions_group",
                        "line_number": 9,
                        "failure_line_number": 17,
                        "reporting_only": True,
                        "automation_allowed": False,
                        "merge_authorized": False,
                    },
                    "diagnosis": {
                        "code": "TEST_FAILURE",
                        "title": "Test failure",
                        "owner_files": [
                            "src/sdetkit/check_intelligence.py",
                            "tests/test_check_intelligence_first_failure.py",
                        ],
                    },
                }
            ],
            "queued_checks": [{"name": "security", "required": True}],
            "startup_failures": [],
            "missing_required_contexts": [],
            "diagnostic_vectors": {"vectors": [{"classification": "test_failure"}]},
            "remediation_plans": {"plans": [{"classification": "review_first"}]},
            "safe_fix_outcome": {"attempted": False},
            "remediation_refresh": {"merge_assessment": "blocked"},
        },
    )

    out = tmp_path / "comment.md"
    bundle_dir = tmp_path / "failure-bundle"

    result = write_comment_body(
        action_report_path=action_report_path,
        check_intelligence_path=check_intelligence_path,
        out=out,
        failure_bundle_out_dir=bundle_dir,
        pr_number=1366,
        head_sha="explicit-head",
        base_sha="explicit-base",
    )

    assert result["out"] == out.as_posix()
    assert result["failure_bundle"]["out_dir"] == bundle_dir.as_posix()
    assert sorted(path.name for path in bundle_dir.iterdir()) == [
        "failure-bundle.json",
        "failure-bundle.md",
        "manifest.json",
    ]

    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    bundle = json.loads((bundle_dir / "failure-bundle.json").read_text(encoding="utf-8"))
    markdown = (bundle_dir / "failure-bundle.md").read_text(encoding="utf-8")

    assert manifest["schema_version"] == "sdetkit.current_head_failure_bundle.v1"
    assert manifest["pr_number"] == 1366
    assert manifest["head_sha"] == "explicit-head"
    assert manifest["base_sha"] == "explicit-base"
    assert manifest["checks_seen"] == 3
    assert manifest["failed_checks"] == 1
    assert manifest["required_queued_checks"] == 1
    assert manifest["review_first"] is True
    assert manifest["safe_fix_allowed"] is False
    assert bundle["first_failures"][0]["line"] == "FAILED tests/test_contract.py::test_contract"
    step = bundle["first_failures"][0][check_intelligence.FAILED_STEP_EVIDENCE_KEY]
    assert step["status"] == "found"
    assert step["command"] == "python -m pytest -q tests/test_contract.py -o addopts="
    assert step["reporting_only"] is True
    assert step["automation_allowed"] is False
    assert "Failed step evidence: `found`" in markdown
    assert "Failed command: `python -m pytest -q tests/test_contract.py -o addopts=`" in markdown
    assert "src/sdetkit/check_intelligence.py" in bundle["owner_files"]
    assert "# Current-head failure evidence bundle" in markdown
    assert "Full CI lane" in markdown


def test_pr_quality_action_report_cli_keeps_bundle_writing_optional(tmp_path):
    action_report_path = _write_json(
        tmp_path / "action-report.json",
        {
            "status": "green",
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "no action required",
            },
            "recommended_actions": [],
            "proof_commands": [],
        },
    )
    check_intelligence_path = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "checks_seen": 1,
            "failed_checks": [],
            "queued_checks": [],
            "startup_failures": [],
            "missing_required_contexts": [],
        },
    )

    out = tmp_path / "comment.md"
    assert (
        main(
            [
                "--action-report",
                str(action_report_path),
                "--check-intelligence",
                str(check_intelligence_path),
                "--out",
                str(out),
            ]
        )
        == 0
    )

    assert out.exists()
    assert not (tmp_path / "failure-bundle").exists()


def test_current_head_failure_bundle_carries_job_step_confirmation() -> None:
    from sdetkit import check_intelligence, current_head_failure_bundle

    bundle = current_head_failure_bundle.build_current_head_failure_bundle(
        pr_number=1484,
        head_sha="head",
        base_sha="base",
        check_intelligence={
            "checks_seen": 1,
            "failed_checks": [
                {
                    "name": "Fast CI lane",
                    "first_failure": {
                        "line": "src/sdetkit/example.py:12: error: Incompatible return value type",
                        "line_number": 3,
                        "tool": "mypy",
                        "kind": "type_contract",
                    },
                    check_intelligence.FAILED_STEP_EVIDENCE_KEY: {
                        "status": "found",
                        "command": "python -m mypy src",
                        "reporting_only": True,
                        "automation_allowed": False,
                    },
                    check_intelligence.JOB_STEP_CONFIRMATION_KEY: {
                        "status": "confirmed",
                        "source": "github_job_steps",
                        "job_step_name": "Run python -m mypy src",
                        "job_step_conclusion": "failure",
                        "log_command": "python -m mypy src",
                        "reporting_only": True,
                        "automation_allowed": False,
                        "merge_authorized": False,
                    },
                }
            ],
        },
    )
    markdown = current_head_failure_bundle.render_current_head_failure_bundle_markdown(bundle)
    confirmation = bundle["first_failures"][0][check_intelligence.JOB_STEP_CONFIRMATION_KEY]

    assert confirmation["status"] == "confirmed"
    assert confirmation["job_step_name"] == "Run python -m mypy src"
    assert "Job step confirmation: `confirmed`" in markdown
    assert "GitHub job step: `Run python -m mypy src`" in markdown
    assert "Job step automation allowed: `false`" in markdown
