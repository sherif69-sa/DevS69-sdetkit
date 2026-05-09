from __future__ import annotations

import json
from pathlib import Path

from sdetkit import ci_failure_triage


def test_pytest_failure_is_actual_blocker_before_coverage_wrapper() -> None:
    log = """
    ============================= FAILURES =============================
    FAILED tests/test_maintenance_cli.py::test_deterministic_mode_is_byte_identical_across_runs - AssertionError: output drift
    E   AssertionError: output drift
    Required test coverage of 95% not reached. Total coverage: 94.7%
    Process completed with exit code 1
    """

    report = ci_failure_triage.build_triage_report(log)

    assert report.classification == "test_failure"
    assert report.blocker is True
    assert "coverage" in report.headline_failure.lower()
    assert (
        report.actual_failure
        == "tests/test_maintenance_cli.py::test_deterministic_mode_is_byte_identical_across_runs - AssertionError: output drift"
    )
    assert report.likely_owner_files[0] == "tests/test_maintenance_cli.py"
    assert "coverage wrapper" in report.noise_to_ignore[0]
    assert report.verification_commands == (
        "python -m pytest -q tests/test_maintenance_cli.py::test_deterministic_mode_is_byte_identical_across_runs -o addopts=",
    )


def test_coverage_only_failure_is_quality_wrapper() -> None:
    report = ci_failure_triage.build_triage_report(
        "Required test coverage of 95% not reached. Total coverage: 94.7%\n"
    )

    assert report.classification == "quality_wrapper"
    assert report.blocker is True
    assert report.actual_failure == report.headline_failure
    assert report.contract_that_failed == "coverage policy"
    assert report.verification_commands == ("python -m pytest --cov",)


def test_mypy_error_reports_owner_file_and_type_contract() -> None:
    report = ci_failure_triage.build_triage_report(
        "src/sdetkit/example.py:12: error: Incompatible return value type\n"
        "Process completed with exit code 1\n"
    )

    assert report.classification == "test_contract_failure"
    assert report.likely_owner_files[0] == "src/sdetkit/example.py"
    assert report.contract_that_failed == "mypy type contract"
    assert report.noise_to_ignore == ("nonzero process exit is a wrapper",)


def test_unknown_log_is_non_blocking() -> None:
    report = ci_failure_triage.build_triage_report("371 passed in 1.23s\n")

    assert report.classification == "unknown"
    assert report.blocker is False
    assert report.next_best_action == "provide a failed job log with the failing step output"


def test_json_output_contains_advisory_contract(tmp_path: Path, capsys) -> None:
    log = tmp_path / "ci.log"
    log.write_text(
        "FAILED tests/test_x.py::test_a - AssertionError: nope\n"
        "Process completed with exit code 1\n",
        encoding="utf-8",
    )

    rc = ci_failure_triage.main(["--log", str(log), "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "sdetkit.ci_failure_triage.v1"
    assert payload["classification"] == "test_failure"
    assert payload["blocker"] is True
    assert payload["verification_commands"] == [
        "python -m pytest -q tests/test_x.py::test_a -o addopts="
    ]


def test_markdown_output_is_operator_readable(tmp_path: Path, capsys) -> None:
    log = tmp_path / "ci.log"
    log.write_text(
        "FAILED tests/test_x.py::test_a - AssertionError: nope\n",
        encoding="utf-8",
    )

    rc = ci_failure_triage.main(["--log", str(log), "--format", "md"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "# CI failure triage" in out
    assert "classification: `test_failure`" in out
    assert "tests/test_x.py::test_a" in out


def test_root_cli_dispatches_triage_ci_arguments(tmp_path: Path, capsys) -> None:
    from sdetkit import cli

    log = tmp_path / "ci.log"
    log.write_text(
        "FAILED tests/test_x.py::test_a - AssertionError: nope\n"
        "Process completed with exit code 1\n",
        encoding="utf-8",
    )

    rc = cli.main(["triage-ci", "--log", str(log), "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "test_failure"
    assert payload["actual_failure"].startswith("tests/test_x.py::test_a")


def test_root_help_keeps_patch_and_triage_ci_commands(capsys) -> None:
    from sdetkit import cli

    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "triage-ci" in out
    assert "patch" in out
