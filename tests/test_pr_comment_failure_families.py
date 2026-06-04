from __future__ import annotations

from sdetkit.pr_comment_failure_families import (
    extract_comment_failure_families,
    render_comment_failure_families,
)


def _families(log: str) -> set[str]:
    return {item.family for item in extract_comment_failure_families(log)}


def test_comment_diagnoses_cli_argument_contract_failure() -> None:
    log = """
    usage: sdetkit [-h] command ...
    sdetkit: error: unrecognized arguments: --format
    """

    assert "cli_invalid_command_or_arguments" in _families(log)


def test_comment_diagnoses_artifact_set_mismatch() -> None:
    log = """
    artifact-set mismatch missing=['operational-readiness-governance-contract.json'] extra=[]
    Error: Process completed with exit code 1.
    """

    assert "artifact_set_mismatch" in _families(log)


def test_comment_diagnoses_schema_version_mismatch() -> None:
    log = """
    "failures": [
      "invalid value/type for key: schema_version"
    ],
    "schema_version": "sdetkit.baseline_summary_contract.v1"
    """

    assert "schema_version_mismatch" in _families(log)


def test_comment_diagnoses_stale_pytest_rename_expectation() -> None:
    log = """
    FAILED tests/test_cli_sdetkit.py::test_product_lane_alias_resolves_to_canonical
    AssertionError: assert ' phase-1 hardening scorer' in ' baseline hardening scorer'
    """

    assert "pytest_stale_rename_expectation" in _families(log)


def test_comment_diagnoses_make_target_wrapper_failure() -> None:
    log = """
    make: *** [Makefile:575: platform-readiness-quality-contract] Error 1
    """

    assert "make_target_contract_failed" in _families(log)


def test_comment_renders_multiple_failure_families() -> None:
    log = """
    sdetkit: error: unrecognized arguments: --format
    artifact-set mismatch missing=['a.json'] extra=[]
    invalid value/type for key: schema_version
    make: *** [Makefile:575: platform-readiness-quality-contract] Error 1
    """

    report = render_comment_failure_families(log)

    assert "cli_invalid_command_or_arguments" in report
    assert "artifact_set_mismatch" in report
    assert "schema_version_mismatch" in report
    assert "make_target_contract_failed" in report


def test_comment_diagnoses_validate_exact_artifact_set_step() -> None:
    log = """
    operational-readiness-governance Validate exact artifact set
    ##[error]Process completed with exit code 1.
    """

    assert "artifact_set_mismatch" in _families(log)
