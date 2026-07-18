from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_product_kpi_model import (
    OBSERVATIONS_SCHEMA,
    REPORT_SCHEMA,
    build_report,
    input_provenance,
)

SOURCE_CONTRACT = Path("docs/contracts/adoption-product-kpi-evidence.v1.json")


def _contract(tmp_path: Path) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(SOURCE_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _metric_ids(contract: Path) -> list[str]:
    payload = json.loads(contract.read_text(encoding="utf-8"))
    return [item["metric_id"] for item in payload["metric_definitions"]]


def _observation(observation_id: str, outcomes: dict[str, str]) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "repository_name": f"repo-{observation_id}",
        "repository_url": f"https://example.invalid/{observation_id}",
        "source_commit_sha": "a" * 40,
        "evidence_path": f"evidence/{observation_id}.json",
        "evidence_sha256": "b" * 64,
        "reviewer_id": "reviewer-1",
        "reviewed_at": "2026-07-18T12:00:00Z",
        "metric_outcomes": outcomes,
        "review_notes": "Reviewed against the retained source artifact.",
    }


def _source(path: Path, observations: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps({"schema_version": OBSERVATIONS_SCHEMA, "observations": observations}),
        encoding="utf-8",
    )
    return path


def test_product_kpi_report_retains_outcomes_and_never_invents_zero_precision(
    tmp_path: Path,
) -> None:
    contract = _contract(tmp_path)
    metric_ids = _metric_ids(contract)
    first = {metric_id: "pass" for metric_id in metric_ids}
    second = {metric_id: "fail" for metric_id in metric_ids}
    first["operator_actionability"] = "unavailable"
    second["operator_actionability"] = "unsupported"
    observations = _source(
        tmp_path / "observations.json",
        [_observation("b", second), _observation("a", first)],
    )

    payload = build_report(
        observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="c" * 40,
    )

    assert payload["schema_version"] == REPORT_SCHEMA
    assert payload["report_status"] == "review_required"
    assert payload["reviewed_observation_count"] == 2
    assert [item["observation_id"] for item in payload["reviewed_observation_index"]] == [
        "a",
        "b",
    ]

    metrics = {metric["metric_id"]: metric for metric in payload["metrics"]}
    discovery = metrics["discovery_precision"]
    assert discovery["reviewed_pass_observations"] == 1
    assert discovery["reviewed_applicable_observations"] == 2
    assert discovery["precision"] == 0.5

    actionability = metrics["operator_actionability"]
    assert actionability["reviewed_applicable_observations"] == 0
    assert actionability["precision"] is None
    assert actionability["status"] == "unavailable"
    assert actionability["outcome_counts"]["unavailable"] == 1
    assert actionability["outcome_counts"]["unsupported"] == 1
    assert "operator_actionability" in payload["metrics_without_applicable_denominator"]
    assert all(value is False for value in payload["authority_boundary"].values())


def test_product_kpi_report_accepts_complete_reviewed_evidence(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    outcomes = {metric_id: "pass" for metric_id in _metric_ids(contract)}
    observations = _source(tmp_path / "observations.json", [_observation("one", outcomes)])

    payload = build_report(
        observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="d" * 40,
    )

    assert payload["report_status"] == "reviewed_evidence_available"
    assert payload["metrics_without_applicable_denominator"] == []
    assert all(metric["precision"] == 1.0 for metric in payload["metrics"])
    assert payload["source_relationships"] == {
        "contract_schema_accepted": True,
        "observations_schema_accepted": True,
        "current_head_bound": True,
    }


def test_product_kpi_report_rejects_missing_or_unknown_metric_outcomes(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    metric_ids = _metric_ids(contract)
    outcomes = {metric_id: "pass" for metric_id in metric_ids[:-1]}
    observations = _source(tmp_path / "observations.json", [_observation("one", outcomes)])

    with pytest.raises(ValueError, match="every contracted metric"):
        build_report(
            observations,
            contract_json=contract,
            root=tmp_path,
            current_head_sha="e" * 40,
        )


def test_product_kpi_report_rejects_invalid_review_provenance(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    outcomes = {metric_id: "pass" for metric_id in _metric_ids(contract)}
    observation = _observation("one", outcomes)
    observation["evidence_sha256"] = "not-a-digest"
    observations = _source(tmp_path / "observations.json", [observation])

    with pytest.raises(ValueError, match="evidence_sha256"):
        build_report(
            observations,
            contract_json=contract,
            root=tmp_path,
            current_head_sha="f" * 40,
        )


def test_product_kpi_input_digest_binds_sources_generator_and_head(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    outcomes = {metric_id: "pass" for metric_id in _metric_ids(contract)}
    observations = _source(tmp_path / "observations.json", [_observation("one", outcomes)])
    generator = tmp_path / "generator.py"
    generator.write_text("generator-v1\n", encoding="utf-8")

    first = input_provenance(
        observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="1" * 40,
        generator_path=generator,
    )
    second = input_provenance(
        observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="1" * 40,
        generator_path=generator,
    )
    assert first == second

    generator.write_text("generator-v2\n", encoding="utf-8")
    changed = input_provenance(
        observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="1" * 40,
        generator_path=generator,
    )
    assert changed["input_digest"] != first["input_digest"]
