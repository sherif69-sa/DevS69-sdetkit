from __future__ import annotations

from pathlib import Path
from typing import Any

from .adoption_product_kpi_model import (
    AUTHORITY_FIELDS,
    DEFAULT_CONTRACT,
    REPORT_SCHEMA,
    authority_boundary,
    build_report,
    load_object,
)


def _stale(reason: str) -> dict[str, Any]:
    return {
        "status": "stale",
        "fresh": False,
        "schema_valid": False,
        "source_schema_valid": False,
        "current_head_valid": False,
        "authority_valid": False,
        "reasons": [reason],
        "recorded_input_digest": "",
        "current_input_digest": "",
        "recorded_head_sha": "",
        "current_head_sha": "",
        "reporting_only": True,
        **authority_boundary(),
    }


def validate_freshness(
    payload: dict[str, Any],
    *,
    observations_json: str | Path,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    expected = build_report(
        observations_json,
        contract_json=contract_json,
        root=root,
        current_head_sha=current_head_sha,
    )
    reasons: list[str] = []
    compared_fields = (
        "schema_version",
        "report_status",
        "input_provenance",
        "source_relationships",
        "reviewed_observation_count",
        "metric_count",
        "metrics",
        "metrics_without_applicable_denominator",
        "outcome_totals",
        "reviewed_observation_index",
        "rules",
        "authority_boundary",
    )
    for field in compared_fields:
        if payload.get(field) != expected.get(field):
            reasons.append(f"{field}_mismatch")
    for field in AUTHORITY_FIELDS:
        if payload.get(field) is not False:
            reasons.append(f"{field}_mismatch")

    recorded = payload.get("input_provenance")
    if not isinstance(recorded, dict):
        recorded = {}
    current = expected["input_provenance"]
    relationships = expected["source_relationships"]
    if not current["current_head_available"]:
        reasons.append("current_head_unavailable")
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "schema_valid": payload.get("schema_version") == REPORT_SCHEMA,
        "source_schema_valid": bool(
            relationships["contract_schema_accepted"]
            and relationships["observations_schema_accepted"]
        ),
        "current_head_valid": bool(
            current["current_head_available"]
            and recorded.get("current_head_sha") == current["current_head_sha"]
        ),
        "authority_valid": all(payload.get(field) is False for field in AUTHORITY_FIELDS)
        and payload.get("authority_boundary") == authority_boundary(),
        "reasons": sorted(set(reasons)),
        "recorded_input_digest": recorded.get("input_digest", ""),
        "current_input_digest": current["input_digest"],
        "recorded_head_sha": recorded.get("current_head_sha", ""),
        "current_head_sha": current["current_head_sha"],
        "reporting_only": True,
        **authority_boundary(),
    }


def check_freshness(
    *,
    report_path: str | Path,
    observations_json: str | Path,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        return _stale("report_missing")
    try:
        payload = load_object(path)
        return validate_freshness(
            payload,
            observations_json=observations_json,
            contract_json=contract_json,
            root=root,
            current_head_sha=current_head_sha,
        )
    except ValueError as exc:
        return _stale(f"source_or_report_invalid:{exc}")


def render_freshness_text(payload: dict[str, Any]) -> str:
    raw_reasons = payload.get("reasons")
    reasons = raw_reasons if isinstance(raw_reasons, list) else []
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"schema_valid={str(bool(payload.get('schema_valid', False))).lower()}",
            f"source_schema_valid={str(bool(payload.get('source_schema_valid', False))).lower()}",
            f"current_head_valid={str(bool(payload.get('current_head_valid', False))).lower()}",
            f"authority_valid={str(bool(payload.get('authority_valid', False))).lower()}",
            f"freshness_reasons={','.join(str(item) for item in reasons) or 'none'}",
            f"recorded_input_digest={payload.get('recorded_input_digest', '')}",
            f"current_input_digest={payload.get('current_input_digest', '')}",
            f"recorded_head_sha={payload.get('recorded_head_sha', '')}",
            f"current_head_sha={payload.get('current_head_sha', '')}",
        ]
    )
