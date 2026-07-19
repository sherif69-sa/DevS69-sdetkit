from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sdetkit.adoption_product_kpi_report import (
    verify_retained_evidence,
    write_artifacts,
)

RECORDS = Path("docs/evidence/adoption-product-kpi/reviewed-kpi-records.v1.json")
SOURCES = {
    "pallets-click-679a7a0-reviewed-001": Path(
        "docs/evidence/adoption-product-kpi/pallets-click-679a7a0-reviewed.json"
    ),
    "devs69-pr2118-first-failure-reviewed-002": Path(
        "docs/evidence/adoption-product-kpi/devs69-pr2118-first-failure-reviewed.json"
    ),
}


def _observations_by_id() -> dict[str, dict]:
    payload = json.loads(RECORDS.read_text(encoding="utf-8"))
    return {item["observation_id"]: item for item in payload["observations"]}


def test_checked_in_kpi_records_bind_every_exact_source_file() -> None:
    payload = json.loads(RECORDS.read_text(encoding="utf-8"))
    observations = _observations_by_id()

    assert payload["schema_version"] == "sdetkit.adoption_product_kpi_observations.v1"
    assert set(observations) == set(SOURCES)

    for observation_id, source in SOURCES.items():
        item = observations[observation_id]
        assert item["evidence_path"] == source.as_posix()
        assert (
            item["evidence_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        )

    verified = verify_retained_evidence(RECORDS, root=".")
    assert {item["observation_id"] for item in verified} == set(SOURCES)


def test_click_record_preserves_external_trial_limitations() -> None:
    item = _observations_by_id()["pallets-click-679a7a0-reviewed-001"]

    assert item["repository_name"] == "pallets/click"
    assert item["source_commit_sha"] == "679a7a0eccbdded7a6e85680bdaaf08003765e01"
    assert item["metric_outcomes"]["discovery_precision"] == "pass"
    assert (
        item["metric_outcomes"]["first_failure_extraction_precision"]
        == "not_applicable"
    )
    assert item["metric_outcomes"]["workspace_ownership_precision"] == "not_applicable"


def test_pr2118_record_exercises_first_failure_and_root_owner_surface() -> None:
    item = _observations_by_id()["devs69-pr2118-first-failure-reviewed-002"]
    evidence = json.loads(SOURCES[item["observation_id"]].read_text(encoding="utf-8"))

    assert item["repository_name"] == "sherif69-sa/DevS69-sdetkit"
    assert item["source_commit_sha"] == "d65afeb0267de9dd3cb8aa643d3aa9db4cc3b3a8"
    assert item["metric_outcomes"]["discovery_precision"] == "not_applicable"
    assert item["metric_outcomes"]["first_failure_extraction_precision"] == "pass"
    assert item["metric_outcomes"]["workspace_ownership_precision"] == "pass"

    context = evidence["source_context"]
    assert context["workflow_checkout_sha"] == item["source_commit_sha"]
    assert context["head_commit_sha"] == "0df3b42b9748aa5a617757d5e335d6eeb78017a3"
    assert context["checkout_ref"] == "refs/remotes/pull/2118/merge"

    failure = evidence["observed_failure"]
    assert failure["failing_step"] == "Lint + tests"
    assert failure["exit_code"] == 1
    assert failure["owner_surface"]["kind"] == "root_repository"
    assert failure["owner_surface"]["primary_owner_file"] == (
        "tests/test_adoption_product_kpi_report.py"
    )
    assert failure["actual_failure"] == (
        "ValueError: observation review-1 evidence file is missing"
    )
    assert evidence["operator_evidence"]["recommended_command"].startswith(
        "python -m pytest -q "
        "tests/test_adoption_product_kpi_report.py::"
        "test_product_kpi_report_module_cli_generates_artifacts"
    )
    assert all(value is False for value in evidence["authority_boundary"].values())


def test_expanded_kpi_report_measures_every_contracted_metric(tmp_path: Path) -> None:
    report = write_artifacts(
        observations_json=RECORDS,
        out=tmp_path / "report.json",
        root=".",
        current_head_sha="a" * 40,
        verify_evidence=True,
    )

    assert report["report_status"] == "reviewed_evidence_available"
    assert report["reviewed_observation_count"] == 2
    assert report["outcome_totals"]["pass"] == 11
    assert report["outcome_totals"]["not_applicable"] == 3
    assert report["metrics_without_applicable_denominator"] == []
    assert all(value is False for value in report["authority_boundary"].values())

    metrics = {item["metric_id"]: item for item in report["metrics"]}
    assert len(metrics) == 7
    assert all(item["status"] == "measured" for item in metrics.values())
    assert all(item["precision"] == 1.0 for item in metrics.values())
    assert (
        metrics["first_failure_extraction_precision"][
            "reviewed_applicable_observations"
        ]
        == 1
    )
    assert (
        metrics["workspace_ownership_precision"]["reviewed_applicable_observations"]
        == 1
    )
