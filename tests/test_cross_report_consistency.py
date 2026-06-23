from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cross_report_consistency as consistency

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
GENERATED_AT = "2026-06-23T00:00:00Z"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _spec(report_id: str) -> consistency.ReportSpec:
    return next(spec for spec in consistency.REPORT_SPECS if spec.report_id == report_id)


def _write_contract_index(root: Path) -> None:
    _write_json(
        root / consistency.CONTRACT_INDEX_PATH,
        {
            "schema_version": "sdetkit.artifact-contract-index.v1",
            "artifacts": [
                {
                    "id": spec.report_id,
                    "path": spec.path,
                    "schema_version": spec.expected_artifact_schema,
                    "required_fields": ["schema_version"],
                    "stability": "advanced",
                }
                for spec in consistency.REPORT_SPECS
            ],
        },
    )


def _report_payload(
    *,
    schema_version: str,
    head: str = HEAD,
    authority_expansion: bool = False,
) -> dict:
    return {
        "schema_version": schema_version,
        "generated_at": GENERATED_AT,
        "current_head_sha": head,
        "source_issue_numbers": [1500],
        "source_run_ids": [27000000000],
        "input_provenance": {
            "generated_at": GENERATED_AT,
            "generated_from_head_sha": head,
            "source_issue_numbers": [1500],
            "source_run_ids": [27000000000],
        },
        "reporting_only": True,
        "repo_mutation": False,
        "issue_mutation_allowed": False,
        "automation_allowed": authority_expansion,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _write_report(root: Path, report_id: str, payload: dict) -> Path:
    spec = _spec(report_id)
    path = root / spec.path
    _write_json(path, payload)
    return path


def test_missing_reports_are_partial_in_discovery_mode(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["schema_version"] == consistency.SCHEMA_VERSION
    assert payload["consistency_status"] == "partial"
    assert payload["mode"] == "discovery"
    assert payload["finding_counts"]["blocking"] == 0
    assert payload["finding_counts"]["partial"] == len(consistency.REPORT_SPECS)
    assert payload["missing_report_count"] == len(consistency.REPORT_SPECS)
    assert payload["reporting_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["security_dismissal_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_missing_reports_block_complete_mode(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        complete=True,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["consistency_status"] == "blocked"
    assert payload["mode"] == "complete"
    assert payload["finding_counts"]["blocking"] == len(consistency.REPORT_SPECS)
    assert {finding["finding_id"] for finding in payload["findings"]} == {"required_report_missing"}


def test_present_schema_mismatch_blocks(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    report_id = "workflow-governance-report-json"
    _write_report(
        tmp_path,
        report_id,
        _report_payload(schema_version="sdetkit.workflow_governance_report.v999"),
    )

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["consistency_status"] == "blocked"
    assert any(
        finding["report_id"] == report_id
        and finding["finding_id"] == "report_schema_mismatch"
        and finding["severity"] == "blocking"
        for finding in payload["findings"]
    )


def test_conflicting_current_heads_block(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    first = "workflow-governance-report-json"
    second = "public-command-surface-report-json"
    _write_report(
        tmp_path,
        first,
        _report_payload(schema_version=_spec(first).expected_artifact_schema, head=HEAD),
    )
    _write_report(
        tmp_path,
        second,
        _report_payload(schema_version=_spec(second).expected_artifact_schema, head=OTHER_HEAD),
    )

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    finding_ids = {finding["finding_id"] for finding in payload["findings"]}
    assert "report_head_mismatch" in finding_ids
    assert "cross_report_head_conflict" in finding_ids
    assert payload["finding_counts"]["blocking"] >= 2


def test_explicit_authority_expansion_blocks(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    report_id = "automation-health-json"
    _write_report(
        tmp_path,
        report_id,
        _report_payload(
            schema_version=_spec(report_id).expected_artifact_schema,
            authority_expansion=True,
        ),
    )

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert any(
        finding["report_id"] == report_id and finding["finding_id"] == "authority_expansion"
        for finding in payload["findings"]
    )
    record = next(item for item in payload["report_records"] if item["report_id"] == report_id)
    assert record["authority_expansions"] == [
        {
            "field": "automation_allowed",
            "location": "top_level",
            "observed": True,
            "expected": False,
        }
    ]


def test_release_public_status_schema_is_the_artifact_contract(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    report_id = "release-anti-hijack-threat-model-json"
    spec = _spec(report_id)
    _write_report(
        tmp_path,
        report_id,
        _report_payload(schema_version=spec.expected_artifact_schema),
    )

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    record = next(item for item in payload["report_records"] if item["report_id"] == report_id)
    assert record["producer_schema_version"] != record["expected_artifact_schema_version"]
    assert record["observed_schema_version"] == spec.expected_artifact_schema
    assert not any(
        finding["report_id"] == report_id and "schema" in finding["finding_id"]
        for finding in payload["findings"]
    )


def test_present_stale_dependency_signal_blocks(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    report_id = "product-maturity-radar-json"
    report = _report_payload(schema_version=_spec(report_id).expected_artifact_schema)
    report["dependency_status"] = {"projection_status": "invalid"}
    _write_report(tmp_path, report_id, report)

    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert any(
        finding["report_id"] == report_id and finding["finding_id"] == "stale_or_invalid_dependency"
        for finding in payload["findings"]
    )


def test_freshness_round_trip_and_input_mutation(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    out = tmp_path / "build/sdetkit/cross-report-consistency.json"

    consistency.write_cross_report_consistency(
        repo_root=tmp_path,
        out=out,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )
    fresh = consistency.check_cross_report_consistency_freshness(
        repo_root=tmp_path,
        report_path=out,
        current_head_sha=HEAD,
    )
    assert fresh["fresh"] is True
    assert fresh["status"] == "fresh"

    report_id = "workflow-governance-report-json"
    _write_report(
        tmp_path,
        report_id,
        _report_payload(schema_version=_spec(report_id).expected_artifact_schema),
    )
    stale = consistency.check_cross_report_consistency_freshness(
        repo_root=tmp_path,
        report_path=out,
        current_head_sha=HEAD,
    )
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]


def test_markdown_exposes_findings_and_authority_boundary(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    payload = consistency.build_cross_report_consistency(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    rendered = consistency.render_cross_report_consistency_markdown(payload)

    assert "# SDETKit cross-report consistency" in rendered
    assert "consistency_status: `partial`" in rendered
    assert "reporting_only: true" in rendered
    assert "merge_authorized: false" in rendered
