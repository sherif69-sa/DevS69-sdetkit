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
    assert intelligence["real_evidence_quality"]["evidence_complete_for_failed_checks"] is True
    assert intelligence["real_evidence_quality"]["evidence_gaps"] == []
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


def test_check_intelligence_summarizes_real_evidence_quality(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "required_contexts": ["required-ci"],
            "check_runs": [
                {
                    "name": "Runtime lane",
                    "status": "completed",
                    "conclusion": "failure",
                    "headSha": "old-head",
                    "currentHeadSha": "new-head",
                    "log": "\n".join(
                        [
                            "Traceback (most recent call last):",
                            '  File "/home/runner/work/repo/src/sdetkit/runtime.py", line 7, in main',
                            "RuntimeError: boom",
                        ]
                    ),
                },
                {
                    "name": "Mystery vendor check",
                    "status": "completed",
                    "conclusion": "failure",
                },
                {
                    "name": "Optional slow lane",
                    "status": "queued",
                    "conclusion": "",
                    "required": False,
                },
            ],
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)
    markdown = check_intelligence.render_action_report(report)

    quality = intelligence["real_evidence_quality"]
    assert quality["schema_version"] == "sdetkit.real_check_evidence_quality.v1"
    assert quality["checks_seen"] == 4
    assert quality["failed_checks"] == 2
    assert quality["failed_with_logs"] == 1
    assert quality["failed_without_logs"] == 1
    assert quality["failed_with_first_failure"] == 1
    assert quality["failed_without_first_failure"] == 1
    assert quality["queued_checks"] == 2
    assert quality["missing_required_contexts"] == 1
    assert quality["stale_failed_check_evidence"] == 1
    assert quality["current_failed_check_evidence"] == 1
    assert quality["evidence_complete_for_failed_checks"] is False
    assert "failed_check_logs_missing" in quality["evidence_gaps"]
    assert "first_failure_not_extracted" in quality["evidence_gaps"]
    assert "stale_failed_check_evidence" in quality["evidence_gaps"]
    assert "required_contexts_missing" in quality["evidence_gaps"]
    assert quality["reporting_only"] is True
    assert quality["automation_allowed"] is False
    assert quality["merge_authorized"] is False

    assert report["evidence"]["real_evidence_quality"] == quality
    assert "Real check evidence quality" in markdown
    assert "Failed checks with logs: `1`" in markdown
    assert "Evidence gaps:" in markdown
    assert "Automation allowed: `false`" in markdown


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
    assert "real_evidence_quality" in report["evidence"]
    assert "SDETKit Check Intelligence Action Report" in markdown
    assert "Real check evidence quality" in markdown


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


def test_check_intelligence_reports_code_scanning_freshness_counts(
    tmp_path: Path,
) -> None:
    current_sha = "abc123"
    checks = _write_json(
        tmp_path / "checks.json",
        {"check_runs": [{"name": "CI", "status": "completed", "conclusion": "success"}]},
    )
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            {
                "number": 10,
                "state": "open",
                "rule": {"id": "py/example", "severity": "warning"},
                "most_recent_instance": {
                    "commit_sha": current_sha,
                    "message": {"text": "Current alert"},
                    "location": {"path": "src/sdetkit/example.py", "start_line": 12},
                },
            },
            {
                "number": 11,
                "state": "open",
                "rule": {"id": "py/example", "severity": "warning"},
                "most_recent_instance": {
                    "commit_sha": "old456",
                    "message": {"text": "Stale alert"},
                    "location": {"path": "src/sdetkit/old.py", "start_line": 20},
                },
            },
            {
                "number": 12,
                "state": "dismissed",
                "rule": {"id": "py/ignored", "severity": "note"},
                "most_recent_instance": {
                    "commit_sha": current_sha,
                    "location": {"path": "src/sdetkit/ignored.py", "start_line": 1},
                },
            },
        ],
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        code_scanning_alerts_json=alerts,
        current_head_sha=current_sha,
    )

    review = intelligence["code_scanning_review"]
    assert review["collected"] is True
    assert review["open_alerts"] == 2
    assert review["current_alerts"] == 1
    assert review["stale_alerts"] == 1
    assert review["unknown_freshness_alerts"] == 0
    assert review["rule_counts"] == {"py/example": 2}
    assert review["findings"][0]["freshness"] == "current"
    assert review["findings"][0]["recommended_action"] == (
        "fix_current_alert_or_dismiss_reviewed_false_positive"
    )
    assert review["findings"][1]["freshness"] == "stale"
    assert review["findings"][1]["recommended_action"] == "wait_for_code_scanning_refresh"

    action = check_intelligence.build_action_report(intelligence)
    assert action["status"] == "review_required"
    assert action["primary_blocker"]["surface"] == "security"
    assert action["primary_blocker"]["code"] == check_intelligence.CODE_SCANNING_CURRENT_ALERT
    assert action["primary_blocker"]["path"] == "src/sdetkit/example.py"
    assert action["primary_blocker"]["line"] == "12"
    assert action["automation"]["allowed"] is False
    assert action["evidence"]["code_scanning_review"]["current_alerts"] == 1


def test_check_intelligence_treats_merge_candidate_code_scanning_alert_as_current(
    tmp_path: Path,
) -> None:
    pr_head_sha = "pr-head-sha"
    merge_candidate_sha = "merge-candidate-sha"
    checks = _write_json(
        tmp_path / "checks.json",
        {"check_runs": [{"name": "CI", "status": "completed", "conclusion": "success"}]},
    )
    alerts = _write_json(
        tmp_path / "alerts.json",
        {
            "collection_status": "collected",
            "alerts": [
                {
                    "number": 1390,
                    "state": "open",
                    "html_url": "https://example.test/code-scanning/1390",
                    "rule": {"id": "py/implicit-string-concatenation-in-list"},
                    "most_recent_instance": {
                        "commit_sha": merge_candidate_sha,
                        "message": {"text": "Implicit string concatenation."},
                        "location": {
                            "path": "src/sdetkit/protected_verifier.py",
                            "start_line": 683,
                        },
                    },
                }
            ],
        },
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        code_scanning_alerts_json=alerts,
        current_head_sha=pr_head_sha,
        merge_candidate_sha=merge_candidate_sha,
    )
    review = intelligence["code_scanning_review"]
    finding = review["findings"][0]

    assert review["current_alerts"] == 1
    assert review["stale_alerts"] == 0
    assert review["merge_candidate_sha"] == merge_candidate_sha
    assert finding["freshness"] == "current"
    assert finding["freshness_basis"] == "merge_candidate"
    assert finding["merge_candidate_sha"] == merge_candidate_sha

    action = check_intelligence.build_action_report(intelligence)
    assert action["status"] == "review_required"
    assert action["primary_blocker"]["surface"] == "security"
    assert action["primary_blocker"]["code"] == check_intelligence.CODE_SCANNING_CURRENT_ALERT


def test_check_intelligence_preserves_unresolved_security_review_findings(
    tmp_path: Path,
) -> None:
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
    review_threads = _write_json(
        tmp_path / "review-threads.json",
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "isResolved": False,
                                    "path": "src/sdetkit/protected_verifier.py",
                                    "line": 141,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "author": {"login": "github-advanced-security"},
                                                "body": (
                                                    "## sdetkit-security-gate / High entropy string\n\n"
                                                    "High-entropy string literal detected."
                                                ),
                                                "url": "https://example.test/security/1251",
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                }
            }
        },
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        review_threads_json=review_threads,
    )
    report = check_intelligence.build_action_report(intelligence)

    assert intelligence["security_review"]["collected"] is True
    assert intelligence["security_review"]["unresolved_findings"] == 1
    assert (
        intelligence["security_review"]["findings"][0]["path"]
        == "src/sdetkit/protected_verifier.py"
    )
    assert report["status"] == "review_required"
    assert report["primary_blocker"]["surface"] == "security"
    assert report["primary_blocker"]["path"] == "src/sdetkit/protected_verifier.py"
    assert report["primary_blocker"]["code"] == "_".join(("SECURITY", "REVIEW", "FINDING"))
    assert report["automation"]["allowed"] is False


def test_check_intelligence_reports_unavailable_code_scanning_collection(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {"check_runs": [{"name": "CI", "status": "completed", "conclusion": "success"}]},
    )
    alerts = _write_json(
        tmp_path / "alerts.json",
        {
            "collection_status": "unavailable",
            "collection_reason": "GitHub code-scanning alerts API was unavailable or not permitted.",
            "alerts": [],
        },
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        code_scanning_alerts_json=alerts,
        current_head_sha="abc123",
    )

    review = intelligence["code_scanning_review"]
    assert review["collected"] is False
    assert review["collection_status"] == "unavailable"
    assert "unavailable or not permitted" in review["collection_reason"]
    assert review["current_alerts"] == 0
    assert review["findings"] == []


def test_check_intelligence_keeps_stale_code_scanning_alert_visible_non_blocking(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {"check_runs": [{"name": "CI", "status": "completed", "conclusion": "success"}]},
    )
    alerts = _write_json(
        tmp_path / "alerts.json",
        {
            "collection_status": "collected",
            "alerts": [
                {
                    "number": 18,
                    "state": "open",
                    "html_url": "https://example.test/code-scanning/18",
                    "rule": {"id": "py/stale-example", "severity": "warning"},
                    "most_recent_instance": {
                        "commit_sha": "previous-sha",
                        "message": {"text": "Stale alert"},
                        "location": {"path": "src/sdetkit/old.py", "start_line": 20},
                    },
                }
            ],
        },
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        code_scanning_alerts_json=alerts,
        current_head_sha="current-sha",
    )
    action = check_intelligence.build_action_report(intelligence)

    assert intelligence["code_scanning_review"]["collected"] is True
    assert intelligence["code_scanning_review"]["current_alerts"] == 0
    assert intelligence["code_scanning_review"]["stale_alerts"] == 1
    assert action["status"] == "green"
    assert action["primary_blocker"] == {}


def test_check_intelligence_associates_collector_log_for_dotted_matrix_version(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Validate (ubuntu-latest / py3.13)",
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "15-validate-ubuntu-latest-py3-13.log",
        "\n".join(
            [
                "Validate (ubuntu-latest / py3.13) FAILED "
                "tests/test_workflow_contract.py::test_uploads_bundle - AssertionError",
                "Validate (ubuntu-latest / py3.13) 1 failed, 20 passed in 1.00s",
                "Validate (ubuntu-latest / py3.13) Process completed with exit code 1.",
            ]
        ),
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )

    failed = intelligence["failed_checks"][0]
    assert failed["log_collected"] is True
    assert failed["first_failure"]["tool"] == "pytest"
    assert failed["first_failure"]["kind"] == "test_failure"
    assert "tests/test_workflow_contract.py" in failed["first_failure"]["line"]
    assert failed["safe_to_auto_fix"] is False


def test_check_intelligence_skips_cache_miss_and_pytest_invocation_before_failed_node(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Validate (macos-latest / py3.13)",
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "09-validate-macos-latest-py3-13.log",
        "\n".join(
            [
                "Validate (macos-latest / py3.13) Cache not found for input keys: macOS-py3.13-abcdef",
                "Validate (macos-latest / py3.13) ##[group]Run python -m pytest -q",
                "Validate (macos-latest / py3.13) python -m pytest -q",
                "Validate (macos-latest / py3.13) FAILED tests/test_widget.py::test_contract - AssertionError",
                "Validate (macos-latest / py3.13) 1 failed, 20 passed in 1.00s",
            ]
        ),
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )

    failed = intelligence["failed_checks"][0]
    first = failed["first_failure"]
    assert failed["log_collected"] is True
    assert first["tool"] == "pytest"
    assert first["kind"] == "test_failure"
    assert "tests/test_widget.py::test_contract" in first["line"]
    assert "Cache not found" not in first["line"]
    assert "python -m pytest" not in first["line"]
    assert failed["diagnosis"]["code"] == "PYTEST_ASSERTION_FAILURE"
    assert failed["safe_to_auto_fix"] is False


def test_check_intelligence_prefers_explicit_pytest_failed_node_over_summary_and_cache_warning(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Validate (macos-latest / py3.13)",
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "09-validate-macos-latest-py3-13.log",
        "\n".join(
            [
                "Validate (macos-latest / py3.13) WARNING: Cache entry deserialization failed, entry ignored",
                "Validate (macos-latest / py3.13) python -m pytest -q",
                "Validate (macos-latest / py3.13) =================================== FAILURES ===================================",
                "Validate (macos-latest / py3.13) FAILED tests/test_widget.py::test_contract - AssertionError",
                "Validate (macos-latest / py3.13) 1 failed, 20 passed in 1.00s",
            ]
        ),
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )

    failed = intelligence["failed_checks"][0]
    first = failed["first_failure"]
    assert failed["log_collected"] is True
    assert first["tool"] == "pytest"
    assert first["kind"] == "test_failure"
    assert "FAILED tests/test_widget.py::test_contract" in first["line"]
    assert "Cache entry deserialization failed" not in first["line"]
    assert "FAILURES" not in first["line"]
    assert failed["diagnosis"]["code"] == "PYTEST_ASSERTION_FAILURE"
    assert failed["safe_to_auto_fix"] is False


def test_check_intelligence_does_not_assign_single_unrelated_log_to_codeql(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {"name": "CodeQL", "status": "completed", "conclusion": "failure"},
                {
                    "name": "PR Quality local quality gate",
                    "status": "completed",
                    "conclusion": "failure",
                },
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "02-pr-quality-local-quality-gate.log",
        "FAILED tests/test_local_quality.py::test_contract - AssertionError\n",
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )
    failed_by_name = {item["name"]: item for item in intelligence["failed_checks"]}

    codeql = failed_by_name["CodeQL"]
    assert codeql["log_collected"] is False
    assert not codeql["first_failure"]
    assert codeql["safe_to_auto_fix"] is False

    local_gate = failed_by_name["PR Quality local quality gate"]
    assert local_gate["log_collected"] is True
    assert local_gate["first_failure"]["tool"] == "pytest"
    assert local_gate["first_failure"]["kind"] == "test_failure"


def test_check_intelligence_does_not_assign_fast_ci_log_to_generic_ci_check(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {"name": "ci", "status": "completed", "conclusion": "failure"},
                {
                    "name": "Fast CI lane (py3.11)",
                    "status": "completed",
                    "conclusion": "failure",
                },
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "01-fast-ci-lane-py3-11.log",
        "FAILED tests/test_fast_lane.py::test_contract - AssertionError\n",
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )
    failed_by_name = {item["name"]: item for item in intelligence["failed_checks"]}

    generic = failed_by_name["ci"]
    assert generic["log_collected"] is False
    assert not generic["first_failure"]
    assert generic["safe_to_auto_fix"] is False

    fast = failed_by_name["Fast CI lane (py3.11)"]
    assert fast["log_collected"] is True
    assert fast["first_failure"]["tool"] == "pytest"
    assert fast["first_failure"]["kind"] == "test_failure"


def test_check_intelligence_routes_ruff_b011_advice_to_ruff_not_pytest(
    tmp_path: Path,
) -> None:
    lint_rule = "".join(("B", "011"))
    assertion_name = "".join(("Assertion", "Error"))
    finding_path = "/".join(("tests", "test_controlled_actions_log_acquisition_probe.py"))
    advice = (
        f"{lint_rule} Do not `assert False` (`python -O` removes these calls), "
        f"raise `{assertion_name}()`"
    )
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.11)",
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )
    logs_dir = tmp_path / "logs"
    _write(
        logs_dir / "01-fast-ci-lane-py3-11.log",
        "\n".join(
            [
                "Run python -m ruff check src tests",
                advice,
                f" --> {finding_path}:2:12",
                "Found 1 error.",
                "No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).",
                "Process completed with exit code 1.",
            ]
        ),
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )
    report = check_intelligence.build_action_report(intelligence)
    failed = intelligence["failed_checks"][0]
    codes = [item["code"] for item in failed["diagnoses"]]

    assert failed["log_collected"] is True
    assert failed["first_failure"]["tool"] == "ruff"
    assert failed["first_failure"]["kind"] == "lint_failure"
    assert f"{lint_rule} Do not `assert False`" in failed["first_failure"]["line"]
    assert failed["diagnosis"]["code"] == "RUFF_LINT_FAILURE"
    assert "PYTEST_ASSERTION_FAILURE" not in codes
    assert failed["safe_to_auto_fix"] is False
    assert report["primary_blocker"]["surface"] == "quality"
    assert report["primary_blocker"]["title"] == "Ruff lint contract failed"
    assert all("unknown test" not in command for command in report["proof_commands"])
    assert report["automation"]["allowed"] is False


def test_canonical_exact_failure_adds_confidence_and_uncertainty_contract() -> None:
    from sdetkit import check_intelligence

    traceback_log = (
        "Run python -m pytest -q\n"
        "Traceback (most recent call last):\n"
        '  File "/workspace/src/sdetkit/example.py", line 42, in execute\n'
        '    raise AssertionError("expected stable output")\n'
        "AssertionError: expected stable output\n"
    )
    exact = check_intelligence._canonical_exact_failure(
        check_intelligence._first_failure_summary(traceback_log)
    )

    assert exact["line"] == "AssertionError: expected stable output"
    assert exact["evidence_quality"] == {
        "confidence": "high",
        "actionable": True,
        "source": "traceback_exception",
        "uncertainty": [],
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    generic = check_intelligence._canonical_exact_failure(
        {
            "line_number": 1,
            "line": "Step failed",
            "tool": "unknown",
            "kind": "failed_step",
            "context": [],
        }
    )
    assert generic["evidence_quality"]["confidence"] == "medium"
    assert generic["evidence_quality"]["actionable"] is False
    assert generic["evidence_quality"]["uncertainty"] == [
        "failure kind is generic or unknown",
        "failure tool is unknown",
    ]
