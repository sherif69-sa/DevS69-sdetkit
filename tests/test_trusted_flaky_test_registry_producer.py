from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.trusted_flaky_test_registry_producer import (
    NO_TEST_OBSERVATIONS,
    SOURCE_CONNECTED,
    build_producer_report,
    build_trusted_registry_evidence,
    main,
    render_markdown,
)


def test_trusted_producer_emits_explicit_no_observation_registry_without_authority() -> None:
    evidence = build_trusted_registry_evidence(
        source_run_id="run-1417",
        source_head_sha="a5545fa1",
    )

    assert evidence["collection_status"] == "collected"
    assert evidence["status"] == "advisory_registry_collected"
    assert evidence["entries"] == []
    assert evidence["summary"]["entry_count"] == 0
    assert evidence["summary"]["observation_status"] == NO_TEST_OBSERVATIONS
    assert evidence["source"]["kind"] == "trusted_main_artifact"
    assert evidence["source"]["workflow"] == "RepoMemory Profile History"
    assert evidence["source"]["observations_collected"] is False
    assert evidence["source"]["observation_status"] == NO_TEST_OBSERVATIONS

    boundary = evidence["decision_boundary"]
    assert boundary["automatic_quarantine_allowed"] is False
    assert boundary["automatic_rerun_allowed"] is False
    assert boundary["current_failure_suppression_allowed"] is False
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False


def test_trusted_producer_rejects_missing_workflow_provenance() -> None:
    with pytest.raises(ValueError, match="source_run_id is required"):
        build_trusted_registry_evidence(source_run_id="", source_head_sha="a5545fa1")

    with pytest.raises(ValueError, match="source_head_sha is required"):
        build_trusted_registry_evidence(source_run_id="run-1417", source_head_sha="")


def test_trusted_producer_report_explains_no_claim_boundary() -> None:
    report = build_producer_report(
        build_trusted_registry_evidence(
            source_run_id="run-1417",
            source_head_sha="a5545fa1",
        )
    )
    markdown = render_markdown(report)

    assert report["status"] == SOURCE_CONNECTED
    assert report["registry"]["observation_count"] == 0
    assert "# Trusted-main flaky-test registry producer" in markdown
    assert "Observation status: `no_test_observations_available`" in markdown
    assert "No flaky-test observations are claimed" in markdown
    assert "Automation allowed: `false`" in markdown


def test_trusted_producer_cli_writes_registry_and_producer_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    out_dir = tmp_path / "trusted-registry"

    rc = main(
        [
            "--source-run-id",
            "run-1417",
            "--source-head-sha",
            "a5545fa1",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    registry = json.loads(
        (out_dir / "flaky-test-registry-evidence.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (out_dir / "trusted-flaky-test-registry-producer.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "trusted-flaky-test-registry-producer.md").read_text(encoding="utf-8")

    assert printed["status"] == SOURCE_CONNECTED
    assert registry["source"]["observation_status"] == NO_TEST_OBSERVATIONS
    assert registry["entries"] == []
    assert report["registry"]["entry_count"] == 0
    assert "Current failure suppression allowed: `false`" in markdown
