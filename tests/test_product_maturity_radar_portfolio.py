from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA
from sdetkit.product_maturity_radar import SCHEMA_VERSION as RADAR_SCHEMA
from sdetkit.product_maturity_radar_portfolio import (
    AUTHORITY_FIELDS,
    SCHEMA_VERSION,
    build_portfolio_report,
    check_freshness,
    write_report,
)

HEAD = "a" * 40
METRIC_IDS = (
    "discovery_precision",
    "first_failure_extraction_precision",
    "workspace_ownership_precision",
    "proof_command_actionability",
    "authority_boundary_preservation",
    "unsafe_authority_rejection",
    "operator_actionability",
)
UNAVAILABLE = {
    "first_failure_extraction_precision",
    "workspace_ownership_precision",
}


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _authority() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _radar_payload(*, authority_expansion: bool = False) -> dict:
    return {
        "schema_version": RADAR_SCHEMA,
        "report_status": "review_required",
        "projection_status": "partial",
        "surface_count": 9,
        "candidate_count": 2,
        "total_score": 31,
        "total_max_score": 36,
        "current_head_sha": HEAD,
        "input_provenance": {
            "input_digest": "1" * 64,
            "generator_schema_version": RADAR_SCHEMA,
            "generated_from_head_sha": HEAD,
        },
        "automation_allowed": authority_expansion,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": {
            "automation_allowed": authority_expansion,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _kpi_payload() -> dict:
    metrics = []
    for metric_id in METRIC_IDS:
        unavailable = metric_id in UNAVAILABLE
        metrics.append(
            {
                "metric_id": metric_id,
                "status": "unavailable" if unavailable else "measured",
                "precision": None if unavailable else 1.0,
                "reviewed_pass_observations": 0 if unavailable else 1,
                "reviewed_applicable_observations": 0 if unavailable else 1,
                "outcome_counts": {
                    "pass": 0 if unavailable else 1,
                    "fail": 0,
                    "unavailable": 0,
                    "malformed": 0,
                    "unsupported": 0,
                    "not_applicable": 1 if unavailable else 0,
                },
            }
        )
    return {
        "schema_version": KPI_REPORT_SCHEMA,
        "report_status": "review_required",
        "reviewed_observation_count": 1,
        "metric_count": 7,
        "metrics": metrics,
        "metrics_without_applicable_denominator": sorted(UNAVAILABLE),
        "outcome_totals": {
            "pass": 5,
            "fail": 0,
            "unavailable": 0,
            "malformed": 0,
            "unsupported": 0,
            "not_applicable": 2,
        },
        "current_head_sha": HEAD,
        "input_provenance": {
            "input_digest": "2" * 64,
            "generator_schema_version": KPI_REPORT_SCHEMA,
            "current_head_sha": HEAD,
        },
        "source_relationships": {
            "contract_schema_accepted": True,
            "observations_schema_accepted": True,
            "current_head_bound": True,
        },
        "authority_boundary": _authority(),
        **_authority(),
    }


def _capability_matrix(*, keep_completed_gap: bool = False) -> dict:
    gaps = [
        {
            "gap_id": "real_repository_kpi_evidence",
            "priority": "P1",
            "review_first": True,
            "title": "legacy gap",
            "exit_criteria": "legacy gap",
            "suggested_owner_files": ["src/sdetkit"],
        }
    ] if keep_completed_gap else []
    return {
        "schema_version": "sdetkit.platform_capability_matrix.v1",
        "product_stage": "local_first_reliability_platform",
        "authority_boundary": _authority(),
        "active_repository_gaps": gaps,
        "capabilities": [
            {
                "capability_id": "reviewed_repository_kpi_evidence",
                "status": "implemented_and_tested",
                "authority": "reporting_only",
                "title": "Reviewed KPI evidence",
                "owner_files": ["src/sdetkit/adoption_product_kpi_model.py"],
                "proof_tests": ["tests/test_adoption_product_kpi_model.py"],
            },
            {
                "capability_id": "product_maturity_kpi_portfolio_projection",
                "status": "implemented_and_tested",
                "authority": "reporting_only",
                "title": "KPI portfolio projection",
                "owner_files": ["src/sdetkit/product_maturity_radar_portfolio.py"],
                "proof_tests": ["tests/test_product_maturity_radar_portfolio.py"],
            },
        ],
        "external_or_manual_blockers": [],
        "intentionally_blocked": [],
    }


def _fixture_paths(tmp_path: Path, *, keep_completed_gap: bool = False) -> dict[str, Path]:
    radar = _write_json(tmp_path / "build" / "radar.json", _radar_payload())
    kpi = _write_json(tmp_path / "build" / "kpi.json", _kpi_payload())
    matrix = _write_json(
        tmp_path / "docs" / "contracts" / "matrix.json",
        _capability_matrix(keep_completed_gap=keep_completed_gap),
    )
    roadmap = tmp_path / "docs" / "roadmap.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "The reviewed real-repository KPI baseline is complete.\n"
        "Artifact: adoption-product-kpi-report.json\n"
        "Next: conservative Azure DevOps proof discovery.\n",
        encoding="utf-8",
    )
    operator = tmp_path / "docs" / "operator.md"
    operator.write_text(
        "product-maturity-radar-portfolio.json\n"
        "reviewed_observation_count\n"
        "metrics_without_applicable_denominator\n",
        encoding="utf-8",
    )
    return {
        "radar_json": radar,
        "kpi_report_json": kpi,
        "capability_matrix_json": matrix,
        "roadmap_markdown": roadmap,
        "operator_guide_markdown": operator,
    }


def test_portfolio_report_integrates_reviewed_kpi_truth_without_inference(
    tmp_path: Path,
) -> None:
    paths = _fixture_paths(tmp_path)

    payload = build_portfolio_report(root=tmp_path, current_head_sha=HEAD, **paths)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["portfolio_status"] == "current"
    assert payload["report_status"] == "review_required"
    assert payload["radar_projection"]["source"]["status"] == "fresh"
    assert payload["reviewed_kpi_evidence"]["source"]["status"] == "fresh"
    assert payload["reviewed_kpi_evidence"]["reviewed_observation_count"] == 1
    assert payload["reviewed_kpi_evidence"]["measured_metric_count"] == 5
    assert payload["reviewed_kpi_evidence"]["unavailable_metric_count"] == 2
    assert payload["reviewed_kpi_evidence"][
        "metrics_without_applicable_denominator"
    ] == sorted(UNAVAILABLE)
    assert payload["reviewed_kpi_evidence"]["broader_maturity_claim_allowed"] is False
    assert payload["capability_matrix"]["status"] == "aligned"
    assert payload["portfolio_documentation"]["status"] == "aligned"
    assert "first_failure_extraction_precision" in payload["operator_summary"][
        "evidence_next_action"
    ]
    assert payload["operator_summary"]["roadmap_next_slice"] == (
        "conservative Azure DevOps proof discovery"
    )
    assert all(payload[field] is False for field in AUTHORITY_FIELDS)
    assert all(value is False for value in payload["authority_boundary"].values())


def test_portfolio_report_blocks_completed_gap_or_authority_expansion(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path, keep_completed_gap=True)
    radar_payload = _radar_payload(authority_expansion=True)
    _write_json(paths["radar_json"], radar_payload)

    payload = build_portfolio_report(root=tmp_path, current_head_sha=HEAD, **paths)

    assert payload["portfolio_status"] == "blocked"
    assert payload["report_status"] == "invalid_dependency"
    assert payload["radar_projection"]["source"]["status"] == "invalid"
    assert payload["capability_matrix"]["status"] == "misaligned"
    assert "completed_kpi_gap_still_active" in payload["blocked_reasons"]
    assert any("authority_boundary_expansion" in reason for reason in payload["blocked_reasons"])
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False


def test_portfolio_report_freshness_binds_all_source_bytes(tmp_path: Path) -> None:
    paths = _fixture_paths(tmp_path)
    out = tmp_path / "build" / "portfolio.json"

    write_report(
        root=tmp_path,
        out=out,
        current_head_sha=HEAD,
        **paths,
    )
    fresh = check_freshness(
        root=tmp_path,
        report_path=out,
        current_head_sha=HEAD,
        **paths,
    )
    assert fresh["fresh"] is True
    assert fresh["portfolio_status"] == "current"

    kpi = json.loads(paths["kpi_report_json"].read_text(encoding="utf-8"))
    kpi["reviewed_observation_count"] = 2
    _write_json(paths["kpi_report_json"], kpi)

    stale = check_freshness(
        root=tmp_path,
        report_path=out,
        current_head_sha=HEAD,
        **paths,
    )
    assert stale["fresh"] is False
    assert "input_provenance_mismatch" in stale["reasons"]
    assert stale["automation_allowed"] is False
    assert stale["merge_authorized"] is False
