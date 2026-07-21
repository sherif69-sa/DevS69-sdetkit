from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA
from sdetkit.formatter_policy_proposal_observation import (
    SCHEMA_VERSION as OBSERVATION_SCHEMA,
)
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
NOT_APPLICABLE_ONCE = {
    "discovery_precision",
    "first_failure_extraction_precision",
    "workspace_ownership_precision",
}
OBSERVATION_METRIC_IDS = (
    "exact_evidence_binding",
    "proposal_scope_clarity",
    "proof_plan_actionability",
    "rollback_clarity",
    "authority_boundary_preservation",
    "operator_usefulness",
)


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
        not_applicable = metric_id in NOT_APPLICABLE_ONCE
        metrics.append(
            {
                "metric_id": metric_id,
                "status": "measured",
                "precision": 1.0,
                "reviewed_pass_observations": 1 if not_applicable else 2,
                "reviewed_applicable_observations": 1 if not_applicable else 2,
                "outcome_counts": {
                    "pass": 1 if not_applicable else 2,
                    "fail": 0,
                    "unavailable": 0,
                    "malformed": 0,
                    "unsupported": 0,
                    "not_applicable": 1 if not_applicable else 0,
                },
            }
        )
    return {
        "schema_version": KPI_REPORT_SCHEMA,
        "report_status": "reviewed_evidence_available",
        "reviewed_observation_count": 2,
        "metric_count": 7,
        "metrics": metrics,
        "metrics_without_applicable_denominator": [],
        "outcome_totals": {
            "pass": 11,
            "fail": 0,
            "unavailable": 0,
            "malformed": 0,
            "unsupported": 0,
            "not_applicable": 3,
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


def _observation_payload() -> dict:
    return {
        "schema_version": OBSERVATION_SCHEMA,
        "report_status": "review_required",
        "reviewed_observation_count": 0,
        "decision_counts": {
            "accept": 0,
            "reject": 0,
            "defer": 0,
            "request_more_evidence": 0,
        },
        "metrics": [
            {
                "metric_id": metric_id,
                "reviewed_pass_observations": 0,
                "reviewed_fail_observations": 0,
                "reviewed_not_applicable_observations": 0,
                "reviewed_applicable_observations": 0,
                "pass_rate": None,
            }
            for metric_id in OBSERVATION_METRIC_IDS
        ],
        "failed_metric_ids": [],
        "false_authority_count": 0,
        "next_human_action": (
            "Review one real formatter policy proposal and retain its exact source artifact."
        ),
        "execution_research_ready": False,
        "branch_execution_lane_active": False,
        "broader_maturity_claim_allowed": False,
        "observations_authorize_current_action": False,
        "current_head_sha": HEAD,
        "input_provenance": {
            "input_digest": "3" * 64,
            "generator_schema_version": OBSERVATION_SCHEMA,
            "current_head_sha": HEAD,
        },
        "authority_boundary": _authority(),
        **_authority(),
    }


def _capability_matrix(*, keep_completed_gap: bool = False) -> dict:
    gaps = [
        {
            "gap_id": "formatter_policy_proposal_reviewed_evidence",
            "priority": "P2",
            "review_first": True,
            "title": "Retain one real reviewed formatter proposal observation",
            "exit_criteria": "Retain one digest-bound reviewed proposal with zero false authority.",
            "suggested_owner_files": [
                "docs/evidence/formatter-policy-proposal/reviewed-observations.v1.json",
                "docs/formatter-policy-proposal-observation.md",
            ],
        }
    ]
    if keep_completed_gap:
        gaps.append(
            {
                "gap_id": "real_repository_kpi_evidence",
                "priority": "P1",
                "review_first": True,
                "title": "legacy gap",
                "exit_criteria": "legacy gap",
                "suggested_owner_files": ["src/sdetkit"],
            }
        )
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
            {
                "capability_id": "formatter_policy_proposal_observation",
                "status": "implemented_and_tested",
                "authority": "reporting_only",
                "title": "Formatter proposal observation",
                "owner_files": ["src/sdetkit/formatter_policy_proposal_observation.py"],
                "proof_tests": ["tests/test_formatter_policy_proposal_observation.py"],
            },
        ],
        "external_or_manual_blockers": [],
        "intentionally_blocked": [],
    }


def _fixture_paths(tmp_path: Path, *, keep_completed_gap: bool = False) -> dict[str, Path]:
    radar = _write_json(tmp_path / "build" / "radar.json", _radar_payload())
    kpi = _write_json(tmp_path / "build" / "kpi.json", _kpi_payload())
    observation = _write_json(
        tmp_path / "build" / "proposal-observation.json", _observation_payload()
    )
    matrix = _write_json(
        tmp_path / "docs" / "contracts" / "matrix.json",
        _capability_matrix(keep_completed_gap=keep_completed_gap),
    )
    roadmap = tmp_path / "docs" / "roadmap.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "The reviewed real-repository KPI baseline is complete.\n"
        "Artifact: adoption-product-kpi-report.json\n"
        "The baseline now contains two reviewed observations.\n"
        "Artifact: formatter-policy-proposal-observation.json\n"
        "Next: `formatter_policy_proposal_reviewed_evidence`.\n",
        encoding="utf-8",
    )
    operator = tmp_path / "docs" / "operator.md"
    operator.write_text(
        "product-maturity-radar-portfolio.json\n"
        "reviewed_observation_count\n"
        "metrics_without_applicable_denominator\n"
        "formatter_policy_proposal_observation\n"
        "`formatter_policy_proposal_reviewed_evidence`\n",
        encoding="utf-8",
    )
    return {
        "radar_json": radar,
        "kpi_report_json": kpi,
        "proposal_observation_report_json": observation,
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
    assert payload["reviewed_kpi_evidence"]["baseline_status"] == "complete_reviewed_baseline"
    assert payload["reviewed_kpi_evidence"]["reviewed_observation_count"] == 2
    assert payload["reviewed_kpi_evidence"]["measured_metric_count"] == 7
    assert payload["reviewed_kpi_evidence"]["unavailable_metric_count"] == 0
    assert payload["reviewed_kpi_evidence"]["metrics_without_applicable_denominator"] == []
    assert payload["reviewed_kpi_evidence"]["outcome_totals"]["pass"] == 11
    assert payload["reviewed_kpi_evidence"]["outcome_totals"]["not_applicable"] == 3
    assert payload["reviewed_kpi_evidence"]["broader_maturity_claim_allowed"] is False
    observation = payload["formatter_policy_proposal_observation"]
    assert observation["source"]["status"] == "fresh"
    assert observation["reviewed_observation_count"] == 0
    assert observation["false_authority_count"] == 0
    assert observation["execution_research_ready"] is False
    assert payload["capability_matrix"]["status"] == "aligned"
    assert (
        payload["capability_matrix"]["formatter_policy_proposal_reviewed_evidence_active"] is True
    )
    assert payload["capability_matrix"]["formatter_policy_proposal_observation_active"] is False
    assert payload["portfolio_documentation"]["status"] == "aligned"
    assert (
        "Review one real formatter policy proposal"
        in payload["operator_summary"]["evidence_next_action"]
    )
    assert payload["operator_summary"]["proposal_reviewed_observation_count"] == 0
    assert payload["operator_summary"]["proposal_false_authority_count"] == 0
    assert (
        payload["operator_summary"]["roadmap_next_slice"]
        == "formatter_policy_proposal_reviewed_evidence"
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
    kpi["reviewed_observation_count"] = 3
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
