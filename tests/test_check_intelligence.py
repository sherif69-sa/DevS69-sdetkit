from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_check_intelligence_reports_green_when_all_checks_pass(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                },
                {
                    "name": "Security",
                    "status": "completed",
                    "conclusion": "success",
                },
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["schema_version"] == check_intelligence.CHECK_INTELLIGENCE_SCHEMA_VERSION
    assert intelligence["checks_seen"] == 2
    assert intelligence["failed_checks"] == []
    assert intelligence["queued_checks"] == []
    assert report["schema_version"] == check_intelligence.ACTION_REPORT_SCHEMA_VERSION
    assert report["status"] == "green"
    assert report["primary_blocker"] == {}
    assert report["automation"]["allowed"] is False


def test_check_intelligence_turns_dependency_check_failure_into_review_required_action(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Install dependencies",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://example.test/checks/install",
                }
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "install-dependencies.log",
        "\n".join(
            [
                "ERROR: Cannot install -r requirements-test.txt because these package versions have conflicting dependencies.",
                "ResolutionImpossible: for help visit https://pip.pypa.io/",
                "Process completed with exit code 1",
            ]
        ),
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["checks_seen"] == 1
    assert len(intelligence["failed_checks"]) == 1
    failed = intelligence["failed_checks"][0]
    assert failed["diagnosis"]["code"] == "PACKAGE_INSTALL_FAILURE"
    assert failed["safe_to_auto_fix"] is False

    assert report["status"] == "review_required"
    assert report["primary_blocker"]["surface"] == "dependency"
    assert report["primary_blocker"]["title"] == "Dependency resolver failed"
    assert report["automation"]["allowed"] is False
    assert "requirements-test.txt" in " ".join(report["proof_commands"])


def test_check_intelligence_marks_ruff_import_sorting_as_safe_fix_available(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "jobs": [
                {
                    "name": "ruff",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "python -m ruff check src tests",
                            "I001 [*] Import block is un-sorted or un-formatted",
                            "--> tests/test_widget.py:1:1",
                            "Found 1 error.",
                            "[*] 1 fixable with the `--fix` option.",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["failed_checks"][0]["diagnosis"]["code"] == "RUFF_FIXABLE_LINT"
    assert intelligence["failed_checks"][0]["safe_to_auto_fix"] is True
    assert report["status"] == "safe_fix_available"
    assert report["primary_blocker"]["surface"] == "quality"
    assert report["automation"]["allowed"] is True
    assert report["automation"]["attempted"] is False
    assert "ruff check --fix" in " ".join(report["recommended_actions"])


def test_check_intelligence_treats_queued_checks_as_incomplete_not_green(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "workflow_runs": [
                {
                    "name": "PR Quality Comment",
                    "status": "queued",
                    "conclusion": "",
                    "required": True,
                    "url": "https://example.test/runs/queued",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["checks_seen"] == 1
    assert intelligence["failed_checks"] == []
    assert intelligence["queued_checks"][0]["name"] == "PR Quality Comment"
    assert intelligence["queued_checks"][0]["required"] is True
    assert report["status"] == "incomplete"
    assert report["primary_blocker"]["surface"] == "workflow"
    assert report["automation"]["allowed"] is False
    assert "queued" in report["primary_blocker"]["impact"]


def test_check_intelligence_cli_writes_json_and_markdown_artifacts(tmp_path: Path, capsys) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {"check_runs": [{"name": "CI", "status": "completed", "conclusion": "success"}]},
    )
    out_dir = tmp_path / "out"

    rc = check_intelligence.main(
        [
            "--checks-json",
            str(checks),
            "--out-dir",
            str(out_dir),
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["check_intelligence"] == (out_dir / "check-intelligence.json").as_posix()
    assert printed["action_report"] == (out_dir / "action-report.json").as_posix()
    assert printed["action_report_markdown"] == (out_dir / "action-report.md").as_posix()

    intelligence = json.loads((out_dir / "check-intelligence.json").read_text(encoding="utf-8"))
    report = json.loads((out_dir / "action-report.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "action-report.md").read_text(encoding="utf-8")

    assert intelligence["checks_seen"] == 1
    assert report["status"] == "green"
    assert "SDETKit Check Intelligence Action Report" in markdown


def test_check_intelligence_prioritizes_actionable_ruff_failure_over_ci_noise(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane py3.12",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "Install project + dev/test extras",
                            "Collecting build",
                            "Collecting twine",
                            "Successfully installed build twine sdetkit",
                            "Generate kit sample artifacts",
                            "release metadata check not requested",
                            "Ruff lint baseline",
                            "Run python -m ruff check src tests",
                            "F841 Local variable `code` is assigned to but never used",
                            "--> src/sdetkit/check_intelligence.py:314:9",
                            "help: Remove assignment to unused variable `code`",
                            "Found 1 error.",
                            "No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).",
                            "Process completed with exit code 1",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    diagnosis = intelligence["failed_checks"][0]["diagnosis"]
    assert diagnosis["code"] == "RUFF_LINT_FAILURE"
    assert report["status"] == "review_required"
    assert report["primary_blocker"]["surface"] == "quality"
    assert report["primary_blocker"]["title"] == "Ruff lint contract failed"
    assert report["automation"]["allowed"] is False
    assert report["primary_blocker"]["code"] != "RELEASE_ARTIFACT_INVALID"


def test_check_intelligence_does_not_block_green_on_optional_queued_checks(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "ci",
                    "status": "completed",
                    "conclusion": "success",
                    "required": True,
                },
                {
                    "name": "Full CI lane",
                    "status": "queued",
                    "conclusion": "",
                    "required": False,
                    "url": "https://example.test/full-ci",
                },
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["queued_checks"][0]["name"] == "Full CI lane"
    assert intelligence["queued_checks"][0]["required"] is False
    assert report["status"] == "green"
    assert report["primary_blocker"] == {}
    assert report["evidence"]["queued_check_count"] == 1
    assert report["evidence"]["required_queued_check_count"] == 0


def test_check_intelligence_blocks_green_on_required_queued_checks(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "ci",
                    "status": "queued",
                    "conclusion": "",
                    "required": True,
                    "url": "https://example.test/ci",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert report["status"] == "incomplete"
    assert report["primary_blocker"]["check"] == "ci"
    assert report["primary_blocker"]["title"] == "Required checks are not complete"
    assert report["evidence"]["required_queued_check_count"] == 1


def test_check_intelligence_synthesizes_missing_required_context_as_blocker(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "required_contexts": ["ci"],
            "check_runs": [
                {
                    "name": "quality",
                    "status": "completed",
                    "conclusion": "success",
                    "required": False,
                }
            ],
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["checks_seen"] == 2
    assert intelligence["required_contexts"] == ["ci"]
    assert intelligence["missing_required_contexts"] == ["ci"]
    assert intelligence["queued_checks"][0]["name"] == "ci"
    assert intelligence["queued_checks"][0]["required"] is True
    assert intelligence["queued_checks"][0]["missing_required_context"] is True

    assert report["status"] == "incomplete"
    assert report["primary_blocker"]["check"] == "ci"
    assert report["primary_blocker"]["title"] == "Required checks are not complete"
    assert report["evidence"]["queued_check_count"] == 1
    assert report["evidence"]["required_queued_check_count"] == 1


def test_check_intelligence_does_not_synthesize_required_context_when_reported(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "required_contexts": ["ci"],
            "check_runs": [
                {
                    "name": "ci",
                    "context": "ci",
                    "status": "completed",
                    "conclusion": "success",
                    "required": True,
                }
            ],
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["checks_seen"] == 1
    assert intelligence["required_contexts"] == ["ci"]
    assert intelligence["missing_required_contexts"] == []
    assert intelligence["queued_checks"] == []
    assert report["status"] == "green"
    assert report["primary_blocker"] == {}


def test_check_intelligence_codeql_failure_gets_security_review_actions(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "CodeQL",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://example.test/check-runs/codeql",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    failed = intelligence["failed_checks"][0]
    assert failed["diagnosis"]["code"] == "CODEQL_SECURITY_REVIEW_REQUIRED"
    assert failed["surface"] == "security"

    assert report["status"] == "review_required"
    assert report["primary_blocker"]["surface"] == "security"
    assert report["primary_blocker"]["code"] == "CODEQL_SECURITY_REVIEW_REQUIRED"
    assert "GitHub Advanced Security" in " ".join(report["recommended_actions"])
    assert "sdetkit security check" in " ".join(report["proof_commands"])


def test_check_intelligence_validate_failure_gets_log_review_actions(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Validate (ubuntu-latest / py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://example.test/check-runs/validate",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    failed = intelligence["failed_checks"][0]
    assert failed["diagnosis"]["code"] == "VALIDATE_JOB_LOG_REVIEW"
    assert failed["surface"] == "workflow"

    assert report["status"] == "review_required"
    assert report["primary_blocker"]["surface"] == "workflow"
    assert report["primary_blocker"]["code"] == "VALIDATE_JOB_LOG_REVIEW"
    assert "first non-setup failure line" in " ".join(report["recommended_actions"])
    assert "python -m pre_commit run -a" in report["proof_commands"]
