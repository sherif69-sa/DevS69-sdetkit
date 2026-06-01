from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_check_intelligence_extracts_first_failure_from_inline_log(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "check-intelligence-inline-log.json",
        {
            "check_runs": [
                {
                    "name": "pre-commit",
                    "status": "completed",
                    "conclusion": "failure",
                    "output": "\n".join(
                        [
                            "check yaml................................Passed",
                            "ruff format..............................Failed",
                            "- hook id: ruff-format",
                            "- files were modified by this hook",
                            "",
                            "1 file reformatted",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)

    failed = intelligence["failed_checks"]
    assert len(failed) == 1
    first_failure = failed[0]["first_failure"]
    assert first_failure["line"] == "ruff format..............................Failed"
    assert first_failure["line_number"] == 2
    assert first_failure["tool"] == "ruff"
    assert first_failure["kind"] == "format_drift"
    assert failed[0]["first_failure_line"] == "ruff format..............................Failed"


def test_check_intelligence_extracts_first_failure_from_logs_dir(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "fast-ci-lane-py3-12.log").write_text(
        "\n".join(
            [
                "Run python -m mypy src",
                "src/sdetkit/example.py:10: error: Incompatible return value type",
                "Found 1 error in 1 file",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )

    first_failure = intelligence["failed_checks"][0]["first_failure"]
    assert (
        first_failure["line"] == "src/sdetkit/example.py:10: error: Incompatible return value type"
    )
    assert first_failure["line_number"] == 2
    assert first_failure["tool"] == "mypy"
    assert first_failure["kind"] == "type_contract"


def test_action_report_preserves_primary_blocker_first_failure(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "ci",
                    "status": "completed",
                    "conclusion": "failure",
                    "output": "Traceback (most recent call last):\nRuntimeError: command failed\n",
                }
            ]
        },
    )
    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)

    primary = report["primary_blocker"]
    assert primary["first_failure_line"] == "RuntimeError: command failed"
    assert primary["first_failure"]["tool"] == "python"
    assert primary["first_failure"]["kind"] == "runtime_failure"


def test_check_intelligence_matches_slugged_log_file_for_check_name(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "fast-ci-lane-py3-12.log").write_text(
        "src/sdetkit/example.py:10: error: Incompatible return value type\n",
        encoding="utf-8",
    )
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks,
        logs_dir=logs_dir,
    )

    failed = intelligence["failed_checks"][0]
    assert failed["log_collected"] is True
    assert failed["first_failure_line"] == (
        "src/sdetkit/example.py:10: error: Incompatible return value type"
    )


def test_check_intelligence_skips_setup_noise_first_failure(tmp_path: Path) -> None:
    from sdetkit.check_intelligence import build_check_intelligence

    checks = tmp_path / "checks.json"
    _write_json(
        checks,
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "PYTEST_ADDOPTS: -n auto",
                            "shell: /usr/bin/bash -e {0}",
                            "src/sdetkit/example.py:10: error: Incompatible return value type",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks)
    first_failure = intelligence["failed_checks"][0]["first_failure"]

    assert (
        first_failure["line"] == "src/sdetkit/example.py:10: error: Incompatible return value type"
    )
    assert first_failure["tool"] == "mypy"
    assert first_failure["kind"] == "type_contract"


def test_action_report_prefers_current_actionable_failure_over_stale_release() -> None:
    from sdetkit.check_intelligence import build_action_report

    report = build_action_report(
        {
            "current_pr_head_sha": "current-sha",
            "failed_checks": [
                {
                    "name": "ci",
                    "head_sha": "old-sha",
                    "current_pr_head_sha": "current-sha",
                    "stale_evidence": True,
                    "safe_to_auto_fix": False,
                    "diagnosis": {
                        "code": "RELEASE_ARTIFACT_INVALID",
                        "title": "Release artifact validation failed",
                    },
                },
                {
                    "name": "autopilot",
                    "head_sha": "current-sha",
                    "current_pr_head_sha": "current-sha",
                    "safe_to_auto_fix": True,
                    "formatter_changed_files": ["src/sdetkit/example.py"],
                    "diagnosis": {
                        "code": "PRE_COMMIT_FORMAT_DRIFT",
                        "title": "Formatter drift blocked pre-commit",
                    },
                    "safe_remediation": {
                        "safe_to_auto_fix": True,
                        "strategy": "run_pre_commit",
                    },
                },
            ],
            "queued_checks": [],
            "startup_failures": [],
        }
    )

    primary = report["primary_blocker"]
    assert primary["check"] == "autopilot"
    assert primary["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert primary["formatter_changed_files"] == ["src/sdetkit/example.py"]
    assert primary["stale_evidence"] is False


def test_check_intelligence_marks_changed_files_gate_fallout(tmp_path: Path) -> None:
    from sdetkit.check_intelligence import build_check_intelligence

    checks = tmp_path / "checks.json"
    _write_json(
        checks,
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                    "changed_files": ["src/sdetkit/current_pr_file.py"],
                    "log": "\n".join(
                        [
                            "fatal: bad object old-sha",
                            "templates/platform_problem/rich/problem.py:1:1: F401 unused import",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]

    assert failed["possible_changed_files_gate_fallout"] is True
    assert failed["outside_changed_files"] == ["templates/platform_problem/rich/problem.py"]


def test_check_intelligence_skips_pip_cache_install_noise_before_real_failure(
    tmp_path: Path,
) -> None:
    from sdetkit.check_intelligence import build_check_intelligence

    checks = tmp_path / "checks.json"
    _write_json(
        checks,
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.11)",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "Using cached pytest-9.0.3-py3-none-any.whl.metadata (7.6 kB)",
                            "Collecting pluggy<2,>=1.5",
                            "Downloading pluggy-1.6.0-py3-none-any.whl",
                            "Installing collected packages: pluggy, pytest",
                            "Successfully installed pluggy-1.6.0 pytest-9.0.3",
                            "FAILED tests/test_real_contract.py::test_real_contract - AssertionError: expected ready",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks)
    first_failure = intelligence["failed_checks"][0]["first_failure"]

    assert first_failure["line"] == (
        "FAILED tests/test_real_contract.py::test_real_contract - AssertionError: expected ready"
    )
    assert "Using cached pytest" not in first_failure["line"]


def test_check_intelligence_skips_build_metadata_noise_before_real_mypy_failure(
    tmp_path: Path,
) -> None:
    from sdetkit.check_intelligence import build_check_intelligence

    checks = tmp_path / "checks.json"
    _write_json(
        checks,
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "Preparing metadata (pyproject.toml): started",
                            "Preparing metadata (pyproject.toml): finished with status 'done'",
                            "Building wheel for package (pyproject.toml): started",
                            "Stored in directory: /tmp/pip-ephem-wheel-cache",
                            "src/sdetkit/example.py:12: error: Incompatible return value type",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks)
    first_failure = intelligence["failed_checks"][0]["first_failure"]

    assert (
        first_failure["line"] == "src/sdetkit/example.py:12: error: Incompatible return value type"
    )
    assert first_failure["tool"] == "mypy"
    assert first_failure["kind"] == "type_contract"


def test_check_intelligence_extracts_pip_audit_dependency_vulnerability_evidence(
    tmp_path: Path,
) -> None:
    from sdetkit.check_intelligence import build_check_intelligence

    checks = tmp_path / "checks.json"
    _write_json(
        checks,
        {
            "check_runs": [
                {
                    "name": "audit",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "##[group]Run python -m pip install -c constraints-ci.txt -e .",
                            "python -m pip install -c constraints-ci.txt -e .",
                            "pip-audit --format json -o pip-audit-report.json -r requirements-test.txt -r requirements-docs.txt --ignore-vuln CVE-2026-4539",
                            "python .github/scripts/check_pip_audit_baseline.py",
                            "Collecting pip-audit==2.10.0",
                            "Using cached pip_audit-2.10.0-py3-none-any.whl.metadata (28 kB)",
                            "Successfully installed pip-audit-2.10.0",
                            "Found 1 known vulnerability in 1 package",
                            "##[error]Process completed with exit code 1.",
                            "name: pip-audit-report",
                            "path: pip-audit-report.json",
                            "Artifact download URL: https://github.com/example/actions/runs/1/artifacts/2",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]

    assert failed["surface"] == "dependency"
    assert failed["code"] == "DEPENDENCY_AUDIT_VULNERABILITY"
    assert failed["title"] == "Dependency audit reported vulnerable packages"
    assert failed["safe_to_auto_fix"] is False
    assert failed["review_first"] is True
    assert failed["first_failure"]["line"] == "Found 1 known vulnerability in 1 package"
    assert failed["first_failure"]["tool"] == "pip-audit"
    assert failed["first_failure"]["kind"] == "dependency_vulnerability"
    assert failed["dependency_audit"]["vulnerability_count"] == 1
    assert failed["dependency_audit"]["package_count"] == 1
    assert failed["dependency_audit"]["report_path"] == "pip-audit-report.json"
    assert failed["dependency_audit"]["artifact_url"].endswith("/artifacts/2")
    assert failed["dependency_audit"]["ignored_vulnerabilities"] == ["CVE-2026-4539"]
    assert failed["dependency_audit"]["command"].startswith("pip-audit --format json")
    assert "constraints-ci.txt" in failed["owner_files"]
    assert "requirements-test.txt" in failed["owner_files"]
    assert "requirements-docs.txt" in failed["owner_files"]


def test_check_intelligence_skips_pip_audit_install_noise_before_summary(tmp_path: Path) -> None:
    from sdetkit.check_intelligence import build_check_intelligence

    checks = tmp_path / "checks.json"
    _write_json(
        checks,
        {
            "check_runs": [
                {
                    "name": "audit",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "Collecting pip-audit==2.10.0",
                            "Using cached pip_audit-2.10.0-py3-none-any.whl.metadata (28 kB)",
                            "Installing collected packages: pip-audit",
                            "Successfully installed pip-audit-2.10.0",
                            "Found 2 known vulnerabilities in 1 package",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks)
    first_failure = intelligence["failed_checks"][0]["first_failure"]

    assert first_failure["line"] == "Found 2 known vulnerabilities in 1 package"
    assert "Using cached" not in first_failure["line"]


def test_check_intelligence_extracts_failed_step_command_evidence(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "##[group]Run python -m mypy src",
                            "python -m mypy src",
                            "src/sdetkit/example.py:12: error: Incompatible return value type",
                            "##[error]Process completed with exit code 1.",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]
    step = failed[check_intelligence.FAILED_STEP_EVIDENCE_KEY]
    quality = intelligence["real_evidence_quality"]

    assert failed["first_failure"]["tool"] == "mypy"
    assert step["status"] == "found"
    assert step["command"] == "python -m mypy src"
    assert step["source"] == "github_actions_group"
    assert step["reporting_only"] is True
    assert step["automation_allowed"] is False
    assert step["merge_authorized"] is False
    assert quality[check_intelligence.FAILED_WITH_STEP_EVIDENCE_KEY] == 1
    assert quality[check_intelligence.FAILED_WITHOUT_STEP_EVIDENCE_KEY] == 0


def test_check_intelligence_confirms_failed_step_with_job_step_metadata(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "##[group]Run python -m mypy src",
                            "python -m mypy src",
                            "src/sdetkit/example.py:12: error: Incompatible return value type",
                        ]
                    ),
                    "steps": [
                        {"name": "Set up Python", "conclusion": "success"},
                        {"name": "Run python -m mypy src", "conclusion": "failure"},
                    ],
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]
    confirmation = failed[check_intelligence.JOB_STEP_CONFIRMATION_KEY]
    quality = intelligence["real_evidence_quality"]

    assert confirmation["status"] == "confirmed"
    assert confirmation["source"] == "github_job_steps"
    assert confirmation["job_step_name"] == "Run python -m mypy src"
    assert confirmation["job_step_conclusion"] == "failure"
    assert confirmation["log_command"] == "python -m mypy src"
    assert confirmation["reporting_only"] is True
    assert confirmation["automation_allowed"] is False
    assert confirmation["merge_authorized"] is False
    assert confirmation["semantic_equivalence_proven"] is False
    assert quality[check_intelligence.JOB_STEP_CONFIRMED_COUNT_KEY] == 1
    assert quality[check_intelligence.JOB_STEP_MISMATCH_COUNT_KEY] == 0
    assert quality[check_intelligence.JOB_STEP_UNAVAILABLE_COUNT_KEY] == 0


def test_check_intelligence_reports_job_step_mismatch(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "##[group]Run python -m mypy src",
                            "python -m mypy src",
                            "src/sdetkit/example.py:12: error: Incompatible return value type",
                        ]
                    ),
                    "steps": [
                        {"name": "Run python -m pytest -q", "conclusion": "failure"},
                    ],
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    confirmation = intelligence["failed_checks"][0][check_intelligence.JOB_STEP_CONFIRMATION_KEY]

    assert confirmation["status"] == "mismatch"
    assert confirmation["job_step_name"] == "Run python -m pytest -q"
    assert confirmation["job_step_conclusion"] == "failure"
    assert confirmation["log_command"] == "python -m mypy src"


def test_check_intelligence_confirms_dependency_audit_artifact_evidence(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "audit",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "pip-audit --format json -o pip-audit-report.json -r requirements-test.txt",
                            "Found 1 known vulnerability in 1 package",
                            "name: pip-audit-report",
                            "path: pip-audit-report.json",
                            "Artifact download URL: "
                            "https://github.com/example/actions/runs/"
                            "1/artifacts/2",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]
    evidence = failed[check_intelligence.ARTIFACT_EVIDENCE_KEY]
    quality = intelligence["real_evidence_quality"]

    assert evidence["status"] == "present"
    assert evidence["expected_artifacts"] == ["pip-audit-report.json"]
    assert evidence["present_artifacts"] == ["pip-audit-report.json"]
    assert evidence["missing_artifacts"] == []
    assert evidence["source"] == "workflow_artifact_url"
    assert evidence["reporting_only"] is True
    assert evidence["automation_allowed"] is False
    assert evidence["merge_authorized"] is False
    assert evidence["semantic_equivalence_proven"] is False
    assert quality[check_intelligence.ARTIFACT_PRESENT_COUNT_KEY] == 1
    assert quality[check_intelligence.ARTIFACT_MISSING_COUNT_KEY] == 0


def test_check_intelligence_reports_missing_dependency_audit_artifact(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "audit",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "pip-audit --format json -o pip-audit-report.json -r requirements-test.txt",
                            "Found 1 known vulnerability in 1 package",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    evidence = intelligence["failed_checks"][0][check_intelligence.ARTIFACT_EVIDENCE_KEY]

    assert evidence["status"] == "missing"
    assert evidence["expected_artifacts"] == ["pip-audit-report.json"]
    assert evidence["missing_artifacts"] == ["pip-audit-report.json"]
    assert evidence["source"] == "absent"
