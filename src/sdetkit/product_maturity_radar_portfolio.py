from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .adoption_product_kpi_model import REPORT_SCHEMA as KPI_REPORT_SCHEMA
from .product_maturity_radar import SCHEMA_VERSION as RADAR_SCHEMA

SCHEMA_VERSION = "sdetkit.product_maturity_radar_portfolio.v1"
DEFAULT_OUT = "build/sdetkit/product-maturity-radar-portfolio.json"
DEFAULT_RADAR = "build/sdetkit/product-maturity-radar.json"
DEFAULT_KPI_REPORT = "build/sdetkit/adoption-product-kpi-report.json"
DEFAULT_CAPABILITY_MATRIX = "docs/contracts/platform-capability-matrix.v1.json"
DEFAULT_ROADMAP = "docs/roadmap/product-roadmap.md"
DEFAULT_OPERATOR_GUIDE = "docs/operator-reviewed-kpi-portfolio-report.md"
GENERATOR_SOURCE = "src/sdetkit/product_maturity_radar_portfolio.py"
MATRIX_SCHEMA = "sdetkit.platform_capability_matrix.v1"
AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "publication_authorized",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)
RADAR_AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)
REQUIRED_CAPABILITIES = (
    "reviewed_repository_kpi_evidence",
    "product_maturity_kpi_portfolio_projection",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid {label} JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected {label} JSON object: {path}")
    return payload


def _display(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_head(root: Path, override: str | None = None) -> str:
    if override is not None:
        value = override.strip().lower()
    else:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        value = completed.stdout.strip().lower() if completed.returncode == 0 else ""
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("current Git head must be a 40-character hexadecimal SHA")
    return value


def _digest_parts(parts: Sequence[tuple[str, bytes]]) -> str:
    hasher = hashlib.sha256()
    for label, content in sorted(parts, key=lambda item: item[0]):
        label_bytes = label.encode("utf-8")
        hasher.update(len(label_bytes).to_bytes(8, "big"))
        hasher.update(label_bytes)
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def _input_provenance(
    *,
    root: Path,
    radar_path: Path,
    kpi_path: Path,
    matrix_path: Path,
    roadmap_path: Path,
    operator_path: Path,
    current_head_sha: str,
    generator_path: Path | None = None,
) -> dict[str, Any]:
    generator = generator_path.resolve() if generator_path is not None else Path(__file__).resolve()
    inputs = {
        "radar_json": radar_path.read_bytes(),
        "kpi_report_json": kpi_path.read_bytes(),
        "capability_matrix_json": matrix_path.read_bytes(),
        "roadmap_markdown": roadmap_path.read_bytes(),
        "operator_guide_markdown": operator_path.read_bytes(),
        "generator": generator.read_bytes(),
        "schema_version": SCHEMA_VERSION.encode("utf-8"),
        "current_head_sha": current_head_sha.encode("utf-8"),
    }
    return {
        "digest_algorithm": "sha256",
        "input_digest": _digest_parts(list(inputs.items())),
        "input_count": len(inputs),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE,
        "generator_sha256": hashlib.sha256(inputs["generator"]).hexdigest(),
        "current_head_sha": current_head_sha,
        "radar_path": _display(root, radar_path),
        "radar_sha256": hashlib.sha256(inputs["radar_json"]).hexdigest(),
        "kpi_report_path": _display(root, kpi_path),
        "kpi_report_sha256": hashlib.sha256(inputs["kpi_report_json"]).hexdigest(),
        "capability_matrix_path": _display(root, matrix_path),
        "capability_matrix_sha256": hashlib.sha256(inputs["capability_matrix_json"]).hexdigest(),
        "roadmap_path": _display(root, roadmap_path),
        "roadmap_sha256": hashlib.sha256(inputs["roadmap_markdown"]).hexdigest(),
        "operator_guide_path": _display(root, operator_path),
        "operator_guide_sha256": hashlib.sha256(inputs["operator_guide_markdown"]).hexdigest(),
    }


def _observed_head(payload: Mapping[str, Any]) -> str:
    provenance = payload.get("input_provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    return str(
        payload.get("current_head_sha")
        or provenance.get("current_head_sha")
        or provenance.get("generated_from_head_sha")
        or ""
    ).strip()


def _source_report_record(
    payload: Mapping[str, Any],
    *,
    source_id: str,
    expected_schema: str,
    current_head_sha: str,
    authority_fields: Sequence[str],
) -> dict[str, Any]:
    provenance = payload.get("input_provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    observed_schema = str(payload.get("schema_version") or "")
    observed_head = _observed_head(payload)
    input_digest = str(provenance.get("input_digest") or "")
    reasons: list[str] = []
    invalid_reasons: list[str] = []
    stale_reasons: list[str] = []

    if observed_schema != expected_schema:
        invalid_reasons.append("schema_version_mismatch")
    if any(payload.get(field) is not False for field in authority_fields):
        invalid_reasons.append("authority_boundary_expansion")
    boundary = payload.get("authority_boundary")
    if isinstance(boundary, Mapping) and any(
        boundary.get(field) is not False for field in authority_fields if field in boundary
    ):
        invalid_reasons.append("nested_authority_boundary_expansion")
    if observed_head != current_head_sha:
        stale_reasons.append("current_head_mismatch")
    if re.fullmatch(r"[0-9a-f]{64}", input_digest) is None:
        stale_reasons.append("input_digest_invalid")
    if provenance.get("generator_schema_version") != expected_schema:
        stale_reasons.append("generator_schema_version_mismatch")

    reasons.extend(invalid_reasons)
    reasons.extend(stale_reasons)
    if invalid_reasons:
        status = "invalid"
    elif stale_reasons:
        status = "stale"
    else:
        status = "fresh"
    return {
        "source_id": source_id,
        "status": status,
        "reasons": sorted(set(reasons)),
        "expected_schema_version": expected_schema,
        "observed_schema_version": observed_schema,
        "current_head_sha": observed_head,
        "input_digest": input_digest,
        "report_status": str(payload.get("report_status") or ""),
        "reporting_only": True,
        "source_authority": False,
    }


def _metric_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, list):
        raise ValueError("KPI report metrics must be a list")
    metrics: list[dict[str, Any]] = []
    measured_count = 0
    unavailable_count = 0
    unavailable_ids: list[str] = []
    for raw in raw_metrics:
        if not isinstance(raw, Mapping):
            raise ValueError("KPI report metrics must contain objects")
        metric_id = str(raw.get("metric_id") or "").strip()
        status = str(raw.get("status") or "").strip()
        denominator = int(raw.get("reviewed_applicable_observations") or 0)
        numerator = int(raw.get("reviewed_pass_observations") or 0)
        precision = raw.get("precision")
        outcome_counts = raw.get("outcome_counts")
        if not metric_id or not isinstance(outcome_counts, Mapping):
            raise ValueError("KPI metrics require ids and outcome counts")
        if status == "measured":
            measured_count += 1
            if denominator <= 0 or precision is None:
                raise ValueError(
                    f"measured KPI metric {metric_id} requires an applicable denominator"
                )
            expected_precision = round(numerator / denominator, 6)
            if float(precision) != expected_precision:
                raise ValueError(f"KPI metric {metric_id} precision does not match its denominator")
        elif status == "unavailable":
            unavailable_count += 1
            unavailable_ids.append(metric_id)
            if denominator != 0 or precision is not None:
                raise ValueError(f"unavailable KPI metric {metric_id} must retain a null precision")
        else:
            raise ValueError(f"unsupported KPI metric status: {status}")
        metrics.append(
            {
                "metric_id": metric_id,
                "status": status,
                "precision": precision,
                "reviewed_pass_observations": numerator,
                "reviewed_applicable_observations": denominator,
                "outcome_counts": dict(
                    sorted((str(key), int(value)) for key, value in outcome_counts.items())
                ),
            }
        )

    reviewed_count = int(payload.get("reviewed_observation_count") or 0)
    if reviewed_count <= 0:
        raise ValueError("KPI portfolio integration requires at least one reviewed observation")
    declared_unavailable = payload.get("metrics_without_applicable_denominator")
    if not isinstance(declared_unavailable, list):
        raise ValueError("KPI report must declare metrics_without_applicable_denominator")
    if sorted(str(item) for item in declared_unavailable) != sorted(unavailable_ids):
        raise ValueError("KPI unavailable metric list does not match metric statuses")

    return {
        "baseline_status": (
            "complete_reviewed_baseline" if unavailable_count == 0 else "partial_reviewed_baseline"
        ),
        "reviewed_observation_count": reviewed_count,
        "metric_count": len(metrics),
        "measured_metric_count": measured_count,
        "unavailable_metric_count": unavailable_count,
        "metrics_without_applicable_denominator": sorted(unavailable_ids),
        "outcome_totals": dict(payload.get("outcome_totals") or {}),
        "metrics": sorted(metrics, key=lambda item: item["metric_id"]),
        "broader_maturity_claim_allowed": False,
        "predictions_are_proof": False,
    }


def _capability_matrix_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if payload.get("schema_version") != MATRIX_SCHEMA:
        reasons.append("capability_matrix_schema_mismatch")
    authority = payload.get("authority_boundary")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False for field in AUTHORITY_FIELDS
    ):
        reasons.append("capability_matrix_authority_expansion")

    raw_capabilities = payload.get("capabilities")
    raw_capabilities = raw_capabilities if isinstance(raw_capabilities, list) else []
    by_id = {
        str(item.get("capability_id")): item
        for item in raw_capabilities
        if isinstance(item, Mapping) and item.get("capability_id")
    }
    missing = [
        capability_id for capability_id in REQUIRED_CAPABILITIES if capability_id not in by_id
    ]
    if missing:
        reasons.append("required_capabilities_missing")
    for capability_id in REQUIRED_CAPABILITIES:
        item = by_id.get(capability_id)
        if item is not None and item.get("status") != "implemented_and_tested":
            reasons.append(f"capability_not_implemented:{capability_id}")

    raw_gaps = payload.get("active_repository_gaps")
    raw_gaps = raw_gaps if isinstance(raw_gaps, list) else []
    active_gap_ids = {
        str(item.get("gap_id"))
        for item in raw_gaps
        if isinstance(item, Mapping) and item.get("gap_id")
    }
    if "real_repository_kpi_evidence" in active_gap_ids:
        reasons.append("completed_kpi_gap_still_active")

    return {
        "status": "aligned" if not reasons else "misaligned",
        "reasons": sorted(set(reasons)),
        "required_capabilities": list(REQUIRED_CAPABILITIES),
        "present_capabilities": sorted(
            capability_id for capability_id in REQUIRED_CAPABILITIES if capability_id in by_id
        ),
        "real_repository_kpi_gap_active": "real_repository_kpi_evidence" in active_gap_ids,
        "authority_valid": "capability_matrix_authority_expansion" not in reasons,
    }


def _documentation_summary(roadmap_text: str, operator_text: str) -> dict[str, Any]:
    roadmap_tokens = (
        "adoption-product-kpi-report.json",
        "reviewed real-repository KPI baseline is complete",
        "expand reviewed KPI denominators",
    )
    operator_tokens = (
        "product-maturity-radar-portfolio.json",
        "reviewed_observation_count",
        "metrics_without_applicable_denominator",
    )
    missing_roadmap = [token for token in roadmap_tokens if token not in roadmap_text]
    missing_operator = [token for token in operator_tokens if token not in operator_text]
    return {
        "status": "aligned" if not missing_roadmap and not missing_operator else "misaligned",
        "missing_roadmap_markers": missing_roadmap,
        "missing_operator_markers": missing_operator,
        "roadmap_next_slice": "expand reviewed KPI denominators",
        "operator_report_documented": not missing_operator,
    }


def build_portfolio_report(
    *,
    root: str | Path = ".",
    radar_json: str | Path = DEFAULT_RADAR,
    kpi_report_json: str | Path = DEFAULT_KPI_REPORT,
    capability_matrix_json: str | Path = DEFAULT_CAPABILITY_MATRIX,
    roadmap_markdown: str | Path = DEFAULT_ROADMAP,
    operator_guide_markdown: str | Path = DEFAULT_OPERATOR_GUIDE,
    current_head_sha: str | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    radar_path = Path(radar_json).resolve()
    kpi_path = Path(kpi_report_json).resolve()
    matrix_path = Path(capability_matrix_json).resolve()
    roadmap_path = Path(roadmap_markdown).resolve()
    operator_path = Path(operator_guide_markdown).resolve()
    head = _resolve_head(repo_root, current_head_sha)

    radar = _load_object(radar_path, label="product maturity radar")
    kpi = _load_object(kpi_path, label="adoption product KPI report")
    matrix = _load_object(matrix_path, label="platform capability matrix")
    try:
        roadmap_text = roadmap_path.read_text(encoding="utf-8")
        operator_text = operator_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("roadmap and operator guide must be readable") from exc

    radar_source = _source_report_record(
        radar,
        source_id="product_maturity_radar",
        expected_schema=RADAR_SCHEMA,
        current_head_sha=head,
        authority_fields=RADAR_AUTHORITY_FIELDS,
    )
    kpi_source = _source_report_record(
        kpi,
        source_id="adoption_product_kpi_report",
        expected_schema=KPI_REPORT_SCHEMA,
        current_head_sha=head,
        authority_fields=AUTHORITY_FIELDS,
    )
    kpi_summary = _metric_summary(kpi)
    matrix_summary = _capability_matrix_summary(matrix)
    docs_summary = _documentation_summary(roadmap_text, operator_text)

    blocked_reasons: list[str] = []
    for source in (radar_source, kpi_source):
        if source["status"] != "fresh":
            blocked_reasons.extend(
                f"{source['source_id']}:{reason}" for reason in source["reasons"]
            )
    if matrix_summary["status"] != "aligned":
        blocked_reasons.extend(matrix_summary["reasons"])
    if docs_summary["status"] != "aligned":
        blocked_reasons.extend(
            [
                *(
                    f"roadmap_marker_missing:{item}"
                    for item in docs_summary["missing_roadmap_markers"]
                ),
                *(
                    f"operator_marker_missing:{item}"
                    for item in docs_summary["missing_operator_markers"]
                ),
            ]
        )

    portfolio_status = "blocked" if blocked_reasons else "current"
    report_status = (
        "invalid_dependency"
        if blocked_reasons
        else "review_required"
        if kpi_summary["unavailable_metric_count"]
        else "reviewed_evidence_available"
    )
    unavailable = kpi_summary["metrics_without_applicable_denominator"]
    evidence_next_action = (
        "Collect reviewed observations for: " + ", ".join(unavailable)
        if unavailable
        else "Continue collecting reviewed external-repository observations before broader claims."
    )
    provenance = _input_provenance(
        root=repo_root,
        radar_path=radar_path,
        kpi_path=kpi_path,
        matrix_path=matrix_path,
        roadmap_path=roadmap_path,
        operator_path=operator_path,
        current_head_sha=head,
        generator_path=Path(generator_path) if generator_path is not None else None,
    )
    boundary = _authority_boundary()

    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": report_status,
        "portfolio_status": portfolio_status,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "current_head_sha": head,
        "input_provenance": provenance,
        "radar_projection": {
            "source": radar_source,
            "projection_status": str(radar.get("projection_status") or "unknown"),
            "report_status": str(radar.get("report_status") or "unknown"),
            "surface_count": int(radar.get("surface_count") or 0),
            "candidate_count": int(radar.get("candidate_count") or 0),
            "total_score": int(radar.get("total_score") or 0),
            "total_max_score": int(radar.get("total_max_score") or 0),
        },
        "reviewed_kpi_evidence": {
            "source": kpi_source,
            **kpi_summary,
        },
        "capability_matrix": matrix_summary,
        "portfolio_documentation": docs_summary,
        "operator_summary": {
            "status": "review_required" if unavailable else "reviewed_evidence_available",
            "reviewed_observation_count": kpi_summary["reviewed_observation_count"],
            "measured_metric_count": kpi_summary["measured_metric_count"],
            "unavailable_metric_count": kpi_summary["unavailable_metric_count"],
            "evidence_next_action": evidence_next_action,
            "roadmap_next_slice": docs_summary["roadmap_next_slice"],
            "decision_rule": (
                "Use measured reviewed metrics only; do not infer unavailable metrics or treat predictions as proof."
            ),
        },
        "rules": {
            "verified_source_reports_only": True,
            "reviewed_observations_only": True,
            "unavailable_metrics_remain_visible": True,
            "predictions_are_proof": False,
            "source_reports_authoritative": False,
            "portfolio_projection_only": True,
            "target_repo_read": False,
            "target_repo_mutation": False,
            "review_first": True,
        },
        "reporting_only": True,
        "projection_only": True,
        "source_authority": False,
        "authority_boundary": boundary,
        **boundary,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    kpi = payload.get("reviewed_kpi_evidence")
    kpi = kpi if isinstance(kpi, Mapping) else {}
    operator = payload.get("operator_summary")
    operator = operator if isinstance(operator, Mapping) else {}
    radar = payload.get("radar_projection")
    radar = radar if isinstance(radar, Mapping) else {}
    matrix = payload.get("capability_matrix")
    matrix = matrix if isinstance(matrix, Mapping) else {}
    docs = payload.get("portfolio_documentation")
    docs = docs if isinstance(docs, Mapping) else {}

    lines = [
        "# SDETKit product maturity radar portfolio report",
        "",
        f"- report_status: `{payload.get('report_status', 'unknown')}`",
        f"- portfolio_status: `{payload.get('portfolio_status', 'unknown')}`",
        f"- current_head_sha: `{payload.get('current_head_sha', '')}`",
        f"- radar_projection_status: `{radar.get('projection_status', 'unknown')}`",
        f"- reviewed_observation_count: `{kpi.get('reviewed_observation_count', 0)}`",
        f"- measured_metric_count: `{kpi.get('measured_metric_count', 0)}`",
        f"- unavailable_metric_count: `{kpi.get('unavailable_metric_count', 0)}`",
        "- reporting_only: true",
        "- projection_only: true",
        "- source_authority: false",
        "",
        "## Reviewed KPI baseline",
        "",
        "| Metric | Status | Precision | Applicable denominator |",
        "| --- | --- | ---: | ---: |",
    ]
    metrics = kpi.get("metrics")
    if isinstance(metrics, list):
        for metric in metrics:
            if not isinstance(metric, Mapping):
                continue
            precision = metric.get("precision")
            precision_text = "null" if precision is None else str(precision)
            lines.append(
                "| {metric_id} | `{status}` | {precision} | {denominator} |".format(
                    metric_id=metric.get("metric_id", ""),
                    status=metric.get("status", ""),
                    precision=precision_text,
                    denominator=metric.get("reviewed_applicable_observations", 0),
                )
            )

    lines.extend(
        [
            "",
            "## Portfolio alignment",
            "",
            f"- capability_matrix_status: `{matrix.get('status', 'unknown')}`",
            f"- roadmap_operator_docs_status: `{docs.get('status', 'unknown')}`",
            f"- roadmap_next_slice: `{operator.get('roadmap_next_slice', '')}`",
            "",
            "## Operator decision",
            "",
            f"- evidence_next_action: {operator.get('evidence_next_action', '')}",
            f"- decision_rule: {operator.get('decision_rule', '')}",
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- publication_authorized: false",
            "- security_dismissal_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    *,
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out is not None else out_path.with_suffix(".md")
    payload = build_portfolio_report(**kwargs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    return payload


def validate_freshness(payload: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    expected = build_portfolio_report(**kwargs)
    reasons: list[str] = []
    for field in (
        "schema_version",
        "report_status",
        "portfolio_status",
        "blocked_reasons",
        "current_head_sha",
        "input_provenance",
        "radar_projection",
        "reviewed_kpi_evidence",
        "capability_matrix",
        "portfolio_documentation",
        "operator_summary",
        "rules",
        "authority_boundary",
    ):
        if payload.get(field) != expected.get(field):
            reasons.append(f"{field}_mismatch")
    for field in AUTHORITY_FIELDS:
        if payload.get(field) is not False:
            reasons.append(f"{field}_mismatch")
    fresh = not reasons and expected["portfolio_status"] == "current"
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "portfolio_status": expected["portfolio_status"],
        "reasons": sorted(set(reasons or expected["blocked_reasons"])),
        "recorded_input_digest": (
            payload.get("input_provenance", {}).get("input_digest", "")
            if isinstance(payload.get("input_provenance"), Mapping)
            else ""
        ),
        "current_input_digest": expected["input_provenance"]["input_digest"],
        "current_head_sha": expected["current_head_sha"],
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "publication_authorized": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def check_freshness(*, report_path: str | Path = DEFAULT_OUT, **kwargs: Any) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        expected = build_portfolio_report(**kwargs)
        return {
            "status": "stale",
            "fresh": False,
            "portfolio_status": expected["portfolio_status"],
            "reasons": ["report_missing"],
            "recorded_input_digest": "",
            "current_input_digest": expected["input_provenance"]["input_digest"],
            "current_head_sha": expected["current_head_sha"],
            "reporting_only": True,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "publication_authorized": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        }
    return validate_freshness(_load_object(path, label="portfolio report"), **kwargs)


def render_freshness_text(payload: Mapping[str, Any]) -> str:
    reasons = payload.get("reasons")
    reasons = reasons if isinstance(reasons, list) else []
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"portfolio_status={payload.get('portfolio_status', 'blocked')}",
            f"freshness_reasons={','.join(str(item) for item in reasons) if reasons else 'none'}",
            f"recorded_input_digest={payload.get('recorded_input_digest', '')}",
            f"current_input_digest={payload.get('current_input_digest', '')}",
            f"current_head_sha={payload.get('current_head_sha', '')}",
            "reporting_only=true",
            "automation_allowed=false",
            "patch_application_allowed=false",
            "publication_authorized=false",
            "security_dismissal_allowed=false",
            "merge_authorized=false",
            "semantic_equivalence_proven=false",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit product-maturity-radar-portfolio",
        description="Project verified reviewed KPI evidence into product portfolio truth.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--radar-json", default=DEFAULT_RADAR)
    parser.add_argument("--kpi-report-json", default=DEFAULT_KPI_REPORT)
    parser.add_argument("--capability-matrix-json", default=DEFAULT_CAPABILITY_MATRIX)
    parser.add_argument("--roadmap-markdown", default=DEFAULT_ROADMAP)
    parser.add_argument("--operator-guide-markdown", default=DEFAULT_OPERATOR_GUIDE)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--check-freshness", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)
    kwargs = {
        "root": ns.root,
        "radar_json": ns.radar_json,
        "kpi_report_json": ns.kpi_report_json,
        "capability_matrix_json": ns.capability_matrix_json,
        "roadmap_markdown": ns.roadmap_markdown,
        "operator_guide_markdown": ns.operator_guide_markdown,
    }

    if ns.check_freshness:
        payload = check_freshness(report_path=ns.out, **kwargs)
        output = (
            json.dumps(payload, indent=2, sort_keys=True)
            if ns.format == "json"
            else render_freshness_text(payload)
        )
        sys.stdout.write(output + "\n")
        return 0 if payload["fresh"] else 1

    payload = write_report(
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        **kwargs,
    )
    output = (
        json.dumps(payload, indent=2, sort_keys=True)
        if ns.format == "json"
        else render_markdown(payload)
    )
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
