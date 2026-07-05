from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.ci_failure_summary import (
    SCHEMA_VERSION,
    build_failure_summary,
    main,
    render_markdown,
)


def _junit_xml() -> str:
    return """
    <testsuites>
      <testsuite name="pytest">
        <testcase classname="tests.test_alpha" name="test_passes" />
        <testcase classname="tests.test_beta" name="test_fails">
          <failure message="assert 1 == 2">Traceback line 1\nTraceback line 2</failure>
        </testcase>
        <testcase classname="tests.test_gamma" name="test_errors">
          <error message="runtime boom">error trace</error>
        </testcase>
        <testcase classname="tests.test_delta" name="test_skips">
          <skipped />
        </testcase>
      </testsuite>
    </testsuites>
    """


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


def test_failure_summary_reports_first_failure_without_changing_outcome(
    tmp_path: Path,
) -> None:
    report = _summary(_write(tmp_path / "junit.xml", _junit_xml()))

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status"] == "failure_observed"
    assert report["source"]["input_read_only"] is True
    assert report["source"]["commands_executed_by_reader"] is False
    assert report["summary"] == {
        "testcase_count": 4,
        "passed": 1,
        "failed": 1,
        "error": 1,
        "skipped": 1,
        "failure_observed": True,
    }
    assert report["first_failure"]["outcome"] == "failed"
    assert report["first_failure"]["classname"] == "tests.test_beta"
    assert report["first_failure"]["name"] == "test_fails"
    assert report["first_failure"]["message"] == "assert 1 == 2"
    assert report["decision_boundary"] == {
        "diagnostic_only": True,
        "flaky_classification_performed": False,
        "automatic_quarantine_allowed": False,
        "automatic_rerun_allowed": False,
        "failure_suppression_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
    }


def test_failure_summary_handles_passing_junit_without_claiming_failure(
    tmp_path: Path,
) -> None:
    junit = _write(
        tmp_path / "junit.xml",
        (
            "<testsuites><testsuite>"
            "<testcase classname='tests.ok' name='test_ok' />"
            "</testsuite></testsuites>"
        ),
    )

    report = _summary(junit)

    assert report["status"] == "no_failure_observed"
    assert report["summary"]["failure_observed"] is False
    assert report["first_failure"] is None
    assert "No failed or errored testcase" in render_markdown(report)


@pytest.mark.parametrize(
    ("filename", "expected_status"),
    [
        ("missing.xml", "junit_xml_missing"),
        ("empty.xml", "junit_xml_empty"),
    ],
)
def test_failure_summary_writes_diagnostic_status_without_junit(
    tmp_path: Path,
    filename: str,
    expected_status: str,
) -> None:
    junit = tmp_path / filename
    if expected_status == "junit_xml_empty":
        junit.write_text("", encoding="utf-8")

    report = _summary(junit)

    assert report["status"] == expected_status
    assert report["summary"]["testcase_count"] == 0
    assert report["decision_boundary"]["failure_suppression_allowed"] is False


def test_failure_summary_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    junit = _write(tmp_path / "junit.xml", _junit_xml())
    out_dir = tmp_path / "summary"

    rc = main(
        [
            "--junit-xml",
            str(junit),
            "--workflow",
            "CI",
            "--job",
            "Full CI lane",
            "--run-id",
            "12345",
            "--head-sha",
            "abc123",
            "--command",
            "bash quality.sh cov",
            "--event-name",
            "pull_request",
            "--ref-name",
            "refs/pull/1/merge",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {
        "artifact_written": True,
        "failure_observed": True,
        "status": "failure_observed",
    }
    report = json.loads((out_dir / "full-suite-failure-summary.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "full-suite-failure-summary.md").read_text(encoding="utf-8")
    assert report["first_failure"]["name"] == "test_fails"
    assert "# Full-suite failure summary" in markdown
    assert "Merge authorized: `false`" in markdown
