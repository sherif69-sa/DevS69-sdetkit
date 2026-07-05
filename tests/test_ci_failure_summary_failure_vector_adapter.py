from __future__ import annotations

from pathlib import Path

from sdetkit.ci_failure_summary import build_failure_summary
from sdetkit.failure_vector_adapters import extract_ci_failure_summary_vector


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _summary(junit_xml: Path) -> dict:
    return build_failure_summary(
        junit_xml=junit_xml,
        workflow="CI",
        job="Full CI lane",
        run_id="12345",
        head_sha="abc123",
        command="bash quality.sh cov",
        event_name="pull_request",
        ref_name="refs/pull/1/merge",
    )


def test_ci_failure_summary_vector_preserves_first_junit_failure_and_boundaries(
    tmp_path: Path,
) -> None:
    junit = _write(
        tmp_path / "junit.xml",
        """
        <testsuites>
          <testsuite name="pytest">
            <testcase classname="tests.test_beta" name="test_fails">
              <failure message="assert 1 == 2">Traceback line 1</failure>
            </testcase>
          </testsuite>
        </testsuites>
        """,
    )

    result = extract_ci_failure_summary_vector(_summary(junit), log_url="artifact://summary")
    payload = result.to_dict()

    assert result.ecosystem == "python"
    assert result.tool == "pytest"
    assert result.confidence == "high"
    assert result.uncertainty == ()
    assert payload["failure_class"] == "test"
    assert payload["command"] == "bash quality.sh cov"
    assert payload["first_failing_line"] == (
        "FAILED tests/test_beta.py::test_fails - assert 1 == 2"
    )
    assert payload["affected_files"] == ["tests/test_beta.py"]
    assert payload["local_repro_command"] == (
        "PYTHONPATH=src python -m pytest -q tests/test_beta.py::test_fails -o addopts="
    )
    assert payload["safe_fix_candidate"] is False
    assert payload["safe_fix_allowed"] is False
    assert payload["contract"]["reporting_only"] is True
    assert payload["contract"]["automation_allowed"] is False
    assert payload["contract"]["patch_application_allowed"] is False
    assert payload["contract"]["merge_authorized"] is False
    assert payload["adapter"]["target_code_execution"] is False


def test_ci_failure_summary_vector_keeps_missing_failure_review_first(
    tmp_path: Path,
) -> None:
    junit = _write(
        tmp_path / "junit.xml",
        "<testsuites><testsuite><testcase classname='tests.ok' name='test_ok' /></testsuite></testsuites>",
    )

    result = extract_ci_failure_summary_vector(_summary(junit))
    payload = result.to_dict()

    assert result.confidence == "low"
    assert result.uncertainty == ("ci_failure_summary_status_no_failure_observed",)
    assert payload["failure_class"] == "unknown"
    assert payload["risk"] == "high"
    assert payload["scope"] == "unknown"
    assert payload["safe_fix_candidate"] is False
    assert payload["safe_fix_allowed"] is False
    assert payload["first_failing_line"] == (
        "no_failure_observed: no failed junit testcase observed"
    )
    assert payload["contract"]["automation_allowed"] is False
    assert payload["contract"]["patch_application_allowed"] is False
    assert payload["adapter"]["target_code_execution"] is False
