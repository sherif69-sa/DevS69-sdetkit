from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from sdetkit.trusted_test_observation_capture import (
    STATUS,
    build_observation_report,
    main,
    render_markdown,
)


def _junit_root() -> ET.Element:
    return ET.fromstring(
        """
        <testsuites>
          <testsuite name="pytest">
            <testcase classname="tests.test_alpha" name="test_passes" />
            <testcase classname="tests.test_alpha" name="test_fails">
              <failure message="failure text must not be copied">trace</failure>
            </testcase>
            <testcase classname="tests.test_beta" name="test_skips">
              <skipped />
            </testcase>
            <testcase classname="tests.test_beta" name="test_errors">
              <error message="error text must not be copied">trace</error>
            </testcase>
          </testsuite>
        </testsuites>
        """
    )


def _report() -> dict:
    return build_observation_report(
        junit_root=_junit_root(),
        source_workflow="CI",
        source_job="Full CI lane",
        source_run_id="run-1418",
        source_head_sha="3d601331",
        event_name="push",
        ref_name="refs/heads/main",
    )


def test_capture_records_raw_trusted_main_outcomes_without_flake_claims() -> None:
    report = _report()

    assert report["status"] == STATUS
    assert report["source"]["trusted_main"] is True
    assert report["source"]["input_read_only"] is True
    assert report["summary"]["observation_count"] == 4
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 1
    assert report["summary"]["error"] == 1
    assert report["summary"]["skipped"] == 1
    assert report["summary"]["flaky_classification_performed"] is False
    assert report["summary"]["raw_test_identity_emitted"] is False
    assert report["source"]["identity_handling"] == "sha256_digest"

    serialized = json.dumps(report)
    assert "failure text" not in serialized
    assert "error text" not in serialized
    assert "tests.test_alpha" not in serialized
    assert "test_fails" not in serialized
    assert all(
        set(observation) == {"test_fingerprint", "outcome"}
        for observation in report["observations"]
    )
    assert all(len(observation["test_fingerprint"]) == 64 for observation in report["observations"])

    boundary = report["decision_boundary"]
    assert boundary["raw_observation_only"] is True
    assert boundary["raw_test_identity_emitted"] is False
    assert boundary["flaky_classification_performed"] is False
    assert boundary["automatic_quarantine_allowed"] is False
    assert boundary["automatic_rerun_allowed"] is False
    assert boundary["current_failure_suppression_allowed"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False


@pytest.mark.parametrize(
    ("event_name", "ref_name", "expected"),
    [
        ("pull_request", "refs/pull/1418/merge", "main push source"),
        ("push", "refs/heads/feature/test", "main push source"),
    ],
)
def test_capture_rejects_non_main_or_pr_observation_sources(
    event_name: str,
    ref_name: str,
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        build_observation_report(
            junit_root=_junit_root(),
            source_workflow="CI",
            source_job="Full CI lane",
            source_run_id="run-1418",
            source_head_sha="3d601331",
            event_name=event_name,
            ref_name=ref_name,
        )


def test_capture_rejects_empty_or_duplicate_testcase_identity() -> None:
    empty = ET.fromstring("<testsuites><testsuite /></testsuites>")
    with pytest.raises(ValueError, match="contains no testcase observations"):
        build_observation_report(
            junit_root=empty,
            source_workflow="CI",
            source_job="Full CI lane",
            source_run_id="run-1418",
            source_head_sha="3d601331",
            event_name="push",
            ref_name="refs/heads/main",
        )

    duplicate = ET.fromstring(
        """
        <testsuites><testsuite>
          <testcase classname="tests.test_alpha" name="test_same" />
          <testcase classname="tests.test_alpha" name="test_same" />
        </testsuite></testsuites>
        """
    )
    with pytest.raises(ValueError, match="duplicate test identities"):
        build_observation_report(
            junit_root=duplicate,
            source_workflow="CI",
            source_job="Full CI lane",
            source_run_id="run-1418",
            source_head_sha="3d601331",
            event_name="push",
            ref_name="refs/heads/main",
        )


def test_capture_markdown_renders_raw_observation_boundary() -> None:
    markdown = render_markdown(_report())

    assert "# Trusted-main test observations" in markdown
    assert "Observations: `4`" in markdown
    assert "Identity handling: `sha256_digest`" in markdown
    assert "Raw test identity emitted: `false`" in markdown
    assert "Flaky classification performed: `false`" in markdown
    assert "Current failure suppression allowed: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_capture_cli_writes_artifacts_without_echoing_source_values(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    junit = tmp_path / "junit.xml"
    out_dir = tmp_path / "observations"
    junit.write_text(ET.tostring(_junit_root(), encoding="unicode"), encoding="utf-8")

    rc = main(
        [
            "--junit-xml",
            str(junit),
            "--source-workflow",
            "CI",
            "--source-job",
            "Full CI lane",
            "--source-run-id",
            "run-sensitive-provenance",
            "--source-head-sha",
            "head-sensitive-provenance",
            "--event-name",
            "push",
            "--ref-name",
            "refs/heads/main",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = capsys.readouterr().out
    assert "run-sensitive-provenance" not in printed
    assert "head-sensitive-provenance" not in printed

    report = json.loads((out_dir / "trusted-test-observations.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "trusted-test-observations.md").read_text(encoding="utf-8")
    assert report["source"]["run_id"] == "run-sensitive-provenance"
    assert report["source"]["head_sha"] == "head-sensitive-provenance"
    assert "Flaky classification performed: `false`" in markdown


def test_capture_never_persists_parameterized_test_values() -> None:
    root = ET.fromstring(
        """
        <testsuites><testsuite>
          <testcase classname="tests.test_auth" name="test_login[value=SHOULD_NOT_LEAK]" />
        </testsuite></testsuites>
        """
    )

    report = build_observation_report(
        junit_root=root,
        source_workflow="CI",
        source_job="Full CI lane",
        source_run_id="run-1418",
        source_head_sha="3d601331",
        event_name="push",
        ref_name="refs/heads/main",
    )
    serialized = json.dumps(report)

    assert "SHOULD_NOT_LEAK" not in serialized
    assert "test_login" not in serialized
    assert "tests.test_auth" not in serialized
    assert report["observations"][0]["outcome"] == "passed"
    assert len(report["observations"][0]["test_fingerprint"]) == 64
