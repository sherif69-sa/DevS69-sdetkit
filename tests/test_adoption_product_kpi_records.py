from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sdetkit.adoption_product_kpi_report import (
    verify_retained_evidence,
    write_artifacts,
)

RECORDS = Path("docs/evidence/adoption-product-kpi/reviewed-kpi-records.v1.json")
SOURCE = Path("docs/evidence/adoption-product-kpi/pallets-click-679a7a0-reviewed.json")


def test_checked_in_click_record_binds_exact_source_file() -> None:
    payload = json.loads(RECORDS.read_text(encoding="utf-8"))
    item = payload["observations"][0]

    assert item["repository_name"] == "pallets/click"
    assert item["source_commit_sha"] == "679a7a0eccbdded7a6e85680bdaaf08003765e01"
    assert item["evidence_path"] == SOURCE.as_posix()
    assert item["evidence_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert (
        verify_retained_evidence(RECORDS, root=".")[0]["observation_id"]
        == item["observation_id"]
    )


def test_first_click_kpi_report_keeps_unexercised_metrics_visible(
    tmp_path: Path,
) -> None:
    report = write_artifacts(
        observations_json=RECORDS,
        out=tmp_path / "report.json",
        root=".",
        current_head_sha="a" * 40,
        verify_evidence=True,
    )

    assert report["report_status"] == "review_required"
    assert report["reviewed_observation_count"] == 1
    assert report["outcome_totals"]["pass"] == 5
    assert report["outcome_totals"]["not_applicable"] == 2
    assert all(value is False for value in report["authority_boundary"].values())

    metrics = {item["metric_id"]: item for item in report["metrics"]}
    measured = [item for item in metrics.values() if item["status"] == "measured"]
    unavailable = [item for item in metrics.values() if item["status"] == "unavailable"]
    assert len(measured) == 5
    assert all(item["precision"] == 1.0 for item in measured)
    assert len(unavailable) == 2
    assert all(item["precision"] is None for item in unavailable)
