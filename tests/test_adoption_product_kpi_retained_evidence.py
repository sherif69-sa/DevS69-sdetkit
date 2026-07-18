from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sdetkit.adoption_product_kpi_report import verify_retained_evidence, write_artifacts

OBSERVATIONS = Path("docs/evidence/adoption-product-kpi/reviewed-observations.v1.json")
EVIDENCE = Path(
    "docs/evidence/adoption-product-kpi/pallets-click-679a7a0-reviewed.json"
)


def test_checked_in_click_observation_binds_exact_retained_evidence() -> None:
    source = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    observation = source["observations"][0]

    assert observation["repository_name"] == "pallets/click"
    assert observation["source_commit_sha"] == "679a7a0eccbdded7a6e85680bdaaf08003765e01"
    assert observation["evidence_path"] == EVIDENCE.as_posix()
    assert observation["evidence_sha256"] == hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    assert verify_retained_evidence(OBSERVATIONS, root=".") == [
        {
            "observation_id": "pallets-click-679a7a0-reviewed-001",
            "evidence_path": EVIDENCE.as_posix(),
            "evidence_sha256": observation["evidence_sha256"],
        }
    ]


def test_first_reviewed_click_kpi_report_keeps_unexercised_metrics_visible(
    tmp_path: Path,
) -> None:
    payload = write_artifacts(
        observations_json=OBSERVATIONS,
        out=tmp_path / "adoption-product-kpi-report.json",
        root=".",
        current_head_sha="a" * 40,
        verify_evidence=True,
    )

    assert payload["report_status"] == "review_required"
    assert payload["reviewed_observation_count"] == 1
    assert payload["outcome_totals"]["pass"] == 5
    assert payload["outcome_totals"]["not_applicable"] == 2
    assert all(value is False for value in payload["authority_boundary"].values())

    metrics = {item["metric_id"]: item for item in payload["metrics"]}
    for metric_id in (
        "discovery_precision",
        "proof_command_actionability",
        "authority_boundary_preservation",
        "unsafe_authority_rejection",
        "operator_actionability",
    ):
        assert metrics[metric_id]["precision"] == 1.0
        assert metrics[metric_id]["reviewed_applicable_observations"] == 1

    for metric_id in (
        "first_failure_extraction_precision",
        "workspace_ownership_precision",
    ):
        assert metrics[metric_id]["precision"] is None
        assert metrics[metric_id]["status"] == "unavailable"
        assert metrics[metric_id]["outcome_counts"]["not_applicable"] == 1


def test_retained_evidence_verifier_fails_closed_on_digest_tampering(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence" / "review.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text('{"reviewed": true}\n', encoding="utf-8")
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adoption_product_kpi_observations.v1",
                "observations": [
                    {
                        "observation_id": "tamper-check",
                        "evidence_path": "evidence/review.json",
                        "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert verify_retained_evidence(observations, root=tmp_path)[0][
        "observation_id"
    ] == "tamper-check"

    evidence.write_text('{"reviewed": false}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="evidence_sha256 mismatch"):
        verify_retained_evidence(observations, root=tmp_path)


def test_retained_evidence_verifier_rejects_paths_outside_repository(
    tmp_path: Path,
) -> None:
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "observation_id": "escape-check",
                        "evidence_path": "../outside.json",
                        "evidence_sha256": "0" * 64,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes repository root"):
        verify_retained_evidence(observations, root=tmp_path)
