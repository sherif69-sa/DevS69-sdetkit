from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import (
    adoption_learning_report,
    automation_health,
    issue_queue_classifier,
    maintenance_queue_rollup,
    product_maturity_radar,
    public_command_surface_report,
    release_anti_hijack_threat_model,
    remediation_readiness_report,
    workflow_governance_report,
)
from .report_provenance import (
    FRESHNESS_AUTHORITY_BOUNDARY,
    attach_provenance,
    build_input_provenance,
    check_report_path,
    collect_source_run_ids,
    normalize_int_ids,
    render_freshness_text,
    resolve_current_head,
)

SCHEMA_VERSION = "sdetkit.cross_report_consistency.v1"
DEFAULT_OUT = "build/sdetkit/cross-report-consistency.json"
GENERATOR_SOURCE = "src/sdetkit/cross_report_consistency.py"
CONTRACT_INDEX_PATH = "docs/artifact-contract-index.json"

CANONICAL_AUTHORITY: dict[str, bool] = {
    "reporting_only": True,
    "repo_mutation": False,
    "issue_mutation_allowed": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


@dataclasses.dataclass(frozen=True)
class ReportSpec:
    report_id: str
    name: str
    path: str
    expected_artifact_schema: str
    producer_schema: str
    family: str
    required_in_complete: bool = True


REPORT_SPECS: tuple[ReportSpec, ...] = (
    ReportSpec(
        "product-maturity-radar-json",
        "product_maturity_radar",
        product_maturity_radar.DEFAULT_OUT,
        product_maturity_radar.SCHEMA_VERSION,
        product_maturity_radar.SCHEMA_VERSION,
        "decision_projection",
    ),
    ReportSpec(
        "public-command-surface-report-json",
        "public_command_surface_report",
        "build/sdetkit/public-command-surface-report.json",
        public_command_surface_report.SCHEMA_VERSION,
        public_command_surface_report.SCHEMA_VERSION,
        "repository_surface",
    ),
    ReportSpec(
        "workflow-governance-report-json",
        "workflow_governance_report",
        "build/sdetkit/workflow-governance-report.json",
        workflow_governance_report.SCHEMA_VERSION,
        workflow_governance_report.SCHEMA_VERSION,
        "repository_surface",
    ),
    ReportSpec(
        "remediation-readiness-report-json",
        "remediation_readiness_report",
        "build/sdetkit/remediation-readiness-report.json",
        remediation_readiness_report.SCHEMA_VERSION,
        remediation_readiness_report.SCHEMA_VERSION,
        "decision_readiness",
    ),
    ReportSpec(
        "adoption-learning-report-json",
        "adoption_learning_report",
        "build/sdetkit/adoption-learning-report.json",
        adoption_learning_report.SCHEMA_VERSION,
        adoption_learning_report.SCHEMA_VERSION,
        "decision_learning",
    ),
    ReportSpec(
        "release-anti-hijack-threat-model-json",
        "release_anti_hijack_public_status",
        "build/sdetkit/release-anti-hijack-threat-model.json",
        release_anti_hijack_threat_model.PUBLIC_STATUS_SCHEMA_VERSION,
        release_anti_hijack_threat_model.SCHEMA_VERSION,
        "release_security",
    ),
    ReportSpec(
        "automation-health-json",
        "automation_health",
        automation_health.DEFAULT_OUT,
        automation_health.SCHEMA_VERSION,
        automation_health.SCHEMA_VERSION,
        "issue_snapshot",
    ),
    ReportSpec(
        "issue-queue-classifier-json",
        "issue_queue_classifier",
        issue_queue_classifier.DEFAULT_OUT,
        issue_queue_classifier.SCHEMA_VERSION,
        issue_queue_classifier.SCHEMA_VERSION,
        "issue_snapshot",
    ),
    ReportSpec(
        "maintenance-queue-rollup-json",
        "maintenance_queue_rollup",
        maintenance_queue_rollup.DEFAULT_OUT,
        maintenance_queue_rollup.SCHEMA_VERSION,
        maintenance_queue_rollup.SCHEMA_VERSION,
        "issue_snapshot",
    ),
)


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, "invalid_json"
    if not isinstance(loaded, dict):
        return None, "invalid_type"
    return loaded, "present"


def _parse_report_overrides(values: Sequence[str]) -> dict[str, str]:
    known = {spec.report_id for spec in REPORT_SPECS}
    overrides: dict[str, str] = {}
    for value in values:
        report_id, separator, raw_path = value.partition("=")
        report_id = report_id.strip()
        raw_path = raw_path.strip()
        if not separator or not report_id or not raw_path:
            raise ValueError("--report-json values must use <report-id>=<path>")
        if report_id not in known:
            supported = ", ".join(sorted(known))
            raise ValueError(f"unknown report id {report_id!r}; supported: {supported}")
        overrides[report_id] = raw_path
    return overrides


def _resolve_report_paths(root: Path, report_json: Sequence[str]) -> dict[str, Path]:
    overrides = _parse_report_overrides(report_json)
    resolved: dict[str, Path] = {}
    for spec in REPORT_SPECS:
        raw = overrides.get(spec.report_id, spec.path)
        path = Path(raw)
        resolved[spec.report_id] = path if path.is_absolute() else root / path
    return resolved


def _contract_entries(root: Path) -> tuple[dict[str, dict[str, Any]], bytes]:
    path = root / CONTRACT_INDEX_PATH
    payload, state = _load_json(path)
    if payload is None:
        marker = json.dumps({"state": state}, sort_keys=True).encode("utf-8")
        return {}, marker
    entries: dict[str, dict[str, Any]] = {}
    raw_entries = payload.get("artifacts", [])
    if isinstance(raw_entries, list):
        for entry in raw_entries:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                entries[entry["id"]] = entry
    return entries, path.read_bytes()


def _get_path(payload: Mapping[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _first_text(payload: Mapping[str, Any], paths: Sequence[str]) -> str:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _first_list(payload: Mapping[str, Any], paths: Sequence[str]) -> list[Any]:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, list):
            return value
    return []


def _head_values(payload: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for path in (
        "current_head_sha",
        "input_provenance.generated_from_head_sha",
        "provenance.generated_from_head_sha",
        "freshness.current_head_sha",
    ):
        value = _get_path(payload, path)
        if isinstance(value, str) and value.strip():
            values.append(value.strip().lower())
    return sorted(set(values))


def _generated_at(payload: Mapping[str, Any]) -> str:
    return _first_text(
        payload,
        (
            "generated_at",
            "input_provenance.generated_at",
            "provenance.generated_at",
        ),
    )


def _valid_generated_at(value: str) -> bool:
    if not value:
        return False
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _authority_observations(payload: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    observations: dict[str, list[dict[str, Any]]] = {}
    containers = (
        ("top_level", payload),
        ("authority_boundary", payload.get("authority_boundary")),
        ("decision_boundary", payload.get("decision_boundary")),
        ("freshness", payload.get("freshness")),
        ("rules", payload.get("rules")),
    )
    for location, container in containers:
        if not isinstance(container, Mapping):
            continue
        for field in CANONICAL_AUTHORITY:
            if field in container:
                observations.setdefault(field, []).append(
                    {"location": location, "value": container[field]}
                )
    return observations


def _authority_expansions(
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    expansions: list[dict[str, Any]] = []
    for field, expected in CANONICAL_AUTHORITY.items():
        for observation in observations.get(field, ()):  # pragma: no branch - tiny loop
            value = observation.get("value")
            if isinstance(value, bool) and value is not expected:
                expansions.append(
                    {
                        "field": field,
                        "location": str(observation.get("location") or ""),
                        "observed": value,
                        "expected": expected,
                    }
                )
    return expansions


def _freshness_signals(payload: Mapping[str, Any]) -> list[str]:
    signals: list[str] = []
    for path in (
        "freshness_status",
        "freshness.status",
        "dependency_status.projection_status",
        "projection_status",
    ):
        value = _get_path(payload, path)
        if isinstance(value, str) and value.lower() in {"stale", "invalid"}:
            signals.append(f"{path}={value.lower()}")
    dependencies = payload.get("report_dependencies")
    if isinstance(dependencies, list):
        for dependency in dependencies:
            if not isinstance(dependency, Mapping):
                continue
            status = str(dependency.get("status") or "").lower()
            if status in {"stale", "invalid"}:
                signals.append(
                    "report_dependencies:{id}={status}".format(
                        id=dependency.get("id", "unknown"),
                        status=status,
                    )
                )
    return sorted(set(signals))


def _add_finding(
    findings: list[dict[str, Any]],
    *,
    finding_id: str,
    severity: str,
    report_id: str,
    summary: str,
    evidence: str,
) -> None:
    findings.append(
        {
            "finding_id": finding_id,
            "severity": severity,
            "report_id": report_id,
            "summary": summary,
            "evidence": evidence,
        }
    )


def _record_report(
    *,
    spec: ReportSpec,
    path: Path,
    payload: dict[str, Any] | None,
    load_state: str,
    contract: Mapping[str, Any] | None,
    live_head: str,
    complete: bool,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    relative_path = path.as_posix()
    record: dict[str, Any] = {
        "report_id": spec.report_id,
        "name": spec.name,
        "family": spec.family,
        "path": relative_path,
        "required_in_complete": spec.required_in_complete,
        "load_state": load_state,
        "producer_schema_version": spec.producer_schema,
        "expected_artifact_schema_version": spec.expected_artifact_schema,
        "observed_schema_version": "",
        "contract_schema_version": "",
        "artifact_sha256": "",
        "generated_at": "",
        "current_head_sha": "",
        "source_issue_numbers": [],
        "source_run_ids": [],
        "freshness_signals": [],
        "authority_observations": {},
        "authority_expansions": [],
        "status": "missing",
        "reasons": [],
    }

    if load_state == "missing":
        severity = "blocking" if complete and spec.required_in_complete else "partial"
        reason = "required_report_missing" if severity == "blocking" else "report_missing"
        record["reasons"] = [reason]
        _add_finding(
            findings,
            finding_id=reason,
            severity=severity,
            report_id=spec.report_id,
            summary="Expected report artifact is absent.",
            evidence=relative_path,
        )
        return record

    if payload is None:
        record["status"] = "invalid"
        record["reasons"] = [load_state]
        _add_finding(
            findings,
            finding_id="report_unreadable",
            severity="blocking",
            report_id=spec.report_id,
            summary="Present report artifact is not a JSON object.",
            evidence=f"path={relative_path} state={load_state}",
        )
        return record

    record["artifact_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    observed_schema = str(payload.get("schema_version") or "")
    record["observed_schema_version"] = observed_schema
    contract_schema = str(contract.get("schema_version") or "") if contract else ""
    record["contract_schema_version"] = contract_schema

    reasons: list[str] = []
    if not observed_schema:
        reasons.append("report_schema_missing")
        _add_finding(
            findings,
            finding_id="report_schema_missing",
            severity="blocking",
            report_id=spec.report_id,
            summary="Present report does not declare schema_version.",
            evidence=relative_path,
        )
    elif observed_schema != spec.expected_artifact_schema:
        reasons.append("report_schema_mismatch")
        _add_finding(
            findings,
            finding_id="report_schema_mismatch",
            severity="blocking",
            report_id=spec.report_id,
            summary="Artifact schema differs from its expected public artifact contract.",
            evidence=(f"expected={spec.expected_artifact_schema} observed={observed_schema}"),
        )

    if contract is None:
        reasons.append("artifact_contract_missing")
        _add_finding(
            findings,
            finding_id="artifact_contract_missing",
            severity="advisory",
            report_id=spec.report_id,
            summary="Artifact-contract index has no entry for this report.",
            evidence=spec.report_id,
        )
    elif contract_schema != spec.expected_artifact_schema:
        reasons.append("artifact_contract_schema_mismatch")
        _add_finding(
            findings,
            finding_id="artifact_contract_schema_mismatch",
            severity="blocking",
            report_id=spec.report_id,
            summary="Artifact-contract schema disagrees with the expected artifact schema.",
            evidence=(f"expected={spec.expected_artifact_schema} contract={contract_schema}"),
        )

    heads = _head_values(payload)
    if len(heads) > 1:
        reasons.append("report_internal_head_conflict")
        _add_finding(
            findings,
            finding_id="report_internal_head_conflict",
            severity="blocking",
            report_id=spec.report_id,
            summary="One report contains conflicting nonempty current-head claims.",
            evidence=",".join(heads),
        )
    if heads:
        record["current_head_sha"] = heads[0]
        invalid_heads = [head for head in heads if re.fullmatch(r"[0-9a-f]{40}", head) is None]
        if invalid_heads:
            reasons.append("report_head_invalid")
            _add_finding(
                findings,
                finding_id="report_head_invalid",
                severity="blocking",
                report_id=spec.report_id,
                summary="Current-head claim is not a full lowercase SHA-1.",
                evidence=",".join(invalid_heads),
            )
        elif any(head != live_head for head in heads):
            reasons.append("report_head_mismatch")
            _add_finding(
                findings,
                finding_id="report_head_mismatch",
                severity="blocking",
                report_id=spec.report_id,
                summary="Current-state report is bound to a head other than live HEAD.",
                evidence=f"live={live_head} report={','.join(heads)}",
            )
    else:
        reasons.append("report_head_missing")
        _add_finding(
            findings,
            finding_id="report_head_missing",
            severity="partial",
            report_id=spec.report_id,
            summary="Report has no normalized current-head claim.",
            evidence=relative_path,
        )

    generated_at = _generated_at(payload)
    record["generated_at"] = generated_at
    if not generated_at:
        reasons.append("generated_at_missing")
        _add_finding(
            findings,
            finding_id="generated_at_missing",
            severity="partial",
            report_id=spec.report_id,
            summary="Report has no normalized generation timestamp.",
            evidence=relative_path,
        )
    elif not _valid_generated_at(generated_at):
        reasons.append("generated_at_invalid")
        _add_finding(
            findings,
            finding_id="generated_at_invalid",
            severity="partial",
            report_id=spec.report_id,
            summary="Report generation timestamp is not timezone-aware ISO-8601.",
            evidence=generated_at,
        )

    issue_numbers = _first_list(
        payload,
        ("source_issue_numbers", "input_provenance.source_issue_numbers"),
    )
    run_ids = _first_list(
        payload,
        ("source_run_ids", "input_provenance.source_run_ids"),
    )
    record["source_issue_numbers"] = normalize_int_ids(issue_numbers)
    record["source_run_ids"] = normalize_int_ids(run_ids)

    observations = _authority_observations(payload)
    expansions = _authority_expansions(observations)
    record["authority_observations"] = observations
    record["authority_expansions"] = expansions
    if expansions:
        reasons.append("authority_expansion")
        _add_finding(
            findings,
            finding_id="authority_expansion",
            severity="blocking",
            report_id=spec.report_id,
            summary="Report explicitly expands a protected authority boundary.",
            evidence=json.dumps(expansions, sort_keys=True, separators=(",", ":")),
        )
    if not observations:
        reasons.append("authority_boundary_missing")
        _add_finding(
            findings,
            finding_id="authority_boundary_missing",
            severity="advisory",
            report_id=spec.report_id,
            summary="Report exposes no normalized authority-boundary fields.",
            evidence=relative_path,
        )

    freshness_signals = _freshness_signals(payload)
    record["freshness_signals"] = freshness_signals
    if freshness_signals:
        reasons.append("stale_or_invalid_dependency")
        _add_finding(
            findings,
            finding_id="stale_or_invalid_dependency",
            severity="blocking",
            report_id=spec.report_id,
            summary="Present report declares stale or invalid evidence.",
            evidence=",".join(freshness_signals),
        )

    record["reasons"] = sorted(set(reasons))
    blocking_reasons = {
        "report_schema_missing",
        "report_schema_mismatch",
        "artifact_contract_schema_mismatch",
        "report_internal_head_conflict",
        "report_head_invalid",
        "report_head_mismatch",
        "authority_expansion",
        "stale_or_invalid_dependency",
    }
    record["status"] = "invalid" if blocking_reasons.intersection(reasons) else "current"
    return record


def _input_provenance(
    *,
    root: Path,
    paths: Mapping[str, Path],
    contract_bytes: bytes,
    records: Sequence[Mapping[str, Any]],
    complete: bool,
    current_head_sha: str | None,
    generated_at: str | None,
) -> dict[str, Any]:
    data_inputs: dict[str, bytes] = {
        "artifact_contract_index": contract_bytes,
        "mode": ("complete" if complete else "discovery").encode("utf-8"),
    }
    for report_id, path in sorted(paths.items()):
        data_inputs[f"report:{report_id}"] = path.read_bytes() if path.is_file() else b"<missing>"

    issue_numbers: list[object] = []
    run_ids: list[object] = []
    artifact_schemas: dict[str, str] = {}
    for record in records:
        issue_numbers.extend(record.get("source_issue_numbers", []))
        run_ids.extend(record.get("source_run_ids", []))
        artifact_schemas[str(record["report_id"])] = str(
            record.get("observed_schema_version") or record.get("load_state") or "unknown"
        )

    generator = Path(__file__).resolve()
    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=generator.read_bytes(),
        data_inputs=data_inputs,
        root=root,
        source_issue_numbers=normalize_int_ids(issue_numbers),
        source_run_ids=collect_source_run_ids(explicit=run_ids),
        input_artifact_schemas=artifact_schemas,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def build_cross_report_consistency(
    repo_root: str | Path = ".",
    *,
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    live_head = resolve_current_head(root, override=current_head_sha)
    paths = _resolve_report_paths(root, report_json)
    contracts, contract_bytes = _contract_entries(root)
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for spec in REPORT_SPECS:
        path = paths[spec.report_id]
        payload, load_state = _load_json(path)
        records.append(
            _record_report(
                spec=spec,
                path=path,
                payload=payload,
                load_state=load_state,
                contract=contracts.get(spec.report_id),
                live_head=live_head,
                complete=complete,
                findings=findings,
            )
        )

    head_to_reports: dict[str, list[str]] = {}
    for record in records:
        head = str(record.get("current_head_sha") or "")
        if head:
            head_to_reports.setdefault(head, []).append(str(record["report_id"]))
    if len(head_to_reports) > 1:
        _add_finding(
            findings,
            finding_id="cross_report_head_conflict",
            severity="blocking",
            report_id="aggregate",
            summary="Present reports bind current-state claims to different Git heads.",
            evidence=json.dumps(head_to_reports, sort_keys=True, separators=(",", ":")),
        )

    findings = sorted(
        findings,
        key=lambda item: (
            {"blocking": 0, "partial": 1, "advisory": 2}.get(str(item["severity"]), 9),
            str(item["report_id"]),
            str(item["finding_id"]),
        ),
    )
    counts = Counter(str(item["severity"]) for item in findings)
    blocking_count = counts.get("blocking", 0)
    partial_count = counts.get("partial", 0)
    if blocking_count:
        consistency_status = "blocked"
    elif partial_count:
        consistency_status = "partial"
    else:
        consistency_status = "current"

    provenance = _input_provenance(
        root=root,
        paths=paths,
        contract_bytes=contract_bytes,
        records=records,
        complete=complete,
        current_head_sha=live_head,
        generated_at=generated_at,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_status": "review_required" if findings else "passed",
        "consistency_status": consistency_status,
        "mode": "complete" if complete else "discovery",
        "report_count": len(records),
        "present_report_count": sum(record["load_state"] == "present" for record in records),
        "missing_report_count": sum(record["load_state"] == "missing" for record in records),
        "finding_counts": {
            "blocking": blocking_count,
            "partial": partial_count,
            "advisory": counts.get("advisory", 0),
        },
        "report_records": records,
        "findings": findings,
        "rules": {
            "read_existing_reports_only": True,
            "dependencies_regenerated": False,
            "missing_reports_block_in_complete_mode": True,
            "missing_reports_are_partial_in_discovery_mode": True,
            "recommendation_text_reconciled": False,
            "review_first": True,
        },
        **FRESHNESS_AUTHORITY_BOUNDARY,
        "authority_boundary": dict(CANONICAL_AUTHORITY),
    }
    return attach_provenance(payload, provenance)


def cross_report_consistency_input_provenance(
    *,
    repo_root: str | Path = ".",
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    live_head = resolve_current_head(root, override=current_head_sha)
    paths = _resolve_report_paths(root, report_json)
    contracts, contract_bytes = _contract_entries(root)
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for spec in REPORT_SPECS:
        path = paths[spec.report_id]
        payload, load_state = _load_json(path)
        records.append(
            _record_report(
                spec=spec,
                path=path,
                payload=payload,
                load_state=load_state,
                contract=contracts.get(spec.report_id),
                live_head=live_head,
                complete=complete,
                findings=findings,
            )
        )
    return _input_provenance(
        root=root,
        paths=paths,
        contract_bytes=contract_bytes,
        records=records,
        complete=complete,
        current_head_sha=live_head,
        generated_at=generated_at,
    )


def check_cross_report_consistency_freshness(
    *,
    repo_root: str | Path = ".",
    report_path: str | Path = DEFAULT_OUT,
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    current = cross_report_consistency_input_provenance(
        repo_root=repo_root,
        report_json=report_json,
        complete=complete,
        current_head_sha=current_head_sha,
    )
    result = check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )
    result["mode"] = "complete" if complete else "discovery"
    return result


def render_cross_report_consistency_markdown(payload: Mapping[str, Any]) -> str:
    counts = payload.get("finding_counts", {})
    lines = [
        "# SDETKit cross-report consistency",
        "",
        f"- consistency_status: `{payload.get('consistency_status', 'unknown')}`",
        f"- mode: `{payload.get('mode', 'discovery')}`",
        f"- generated_at: `{payload.get('generated_at', '')}`",
        f"- current_head_sha: `{payload.get('current_head_sha', '')}`",
        f"- present_report_count: `{payload.get('present_report_count', 0)}`",
        f"- missing_report_count: `{payload.get('missing_report_count', 0)}`",
        f"- blocking_findings: `{counts.get('blocking', 0)}`",
        f"- partial_findings: `{counts.get('partial', 0)}`",
        f"- advisory_findings: `{counts.get('advisory', 0)}`",
        "",
        "## Report records",
        "",
        "| Report | Status | Schema | Head | Artifact SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in payload.get("report_records", []):
        if not isinstance(record, Mapping):
            continue
        lines.append(
            "| {report} | `{status}` | `{schema}` | `{head}` | `{digest}` |".format(
                report=record.get("report_id", ""),
                status=record.get("status", ""),
                schema=record.get("observed_schema_version", ""),
                head=record.get("current_head_sha", ""),
                digest=record.get("artifact_sha256", ""),
            )
        )
    lines.extend(["", "## Findings", ""])
    findings = payload.get("findings", [])
    if not findings:
        lines.append("- none")
    else:
        for finding in findings:
            if not isinstance(finding, Mapping):
                continue
            lines.append(
                "- **{severity}** `{report}:{finding}` — {summary} ({evidence})".format(
                    severity=finding.get("severity", "unknown"),
                    report=finding.get("report_id", "unknown"),
                    finding=finding.get("finding_id", "unknown"),
                    summary=finding.get("summary", ""),
                    evidence=finding.get("evidence", ""),
                )
            )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- reporting_only: true",
            "- repo_mutation: false",
            "- issue_mutation_allowed: false",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- security_dismissal_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_cross_report_consistency(
    *,
    repo_root: str | Path,
    out: str | Path,
    markdown_out: str | Path | None = None,
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out is not None else out_path.with_suffix(".md")
    payload = build_cross_report_consistency(
        repo_root,
        report_json=report_json,
        complete=complete,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_cross_report_consistency_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit cross-report-consistency",
        description="Detect schema, head, freshness, and authority contradictions across reports.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument(
        "--report-json",
        action="append",
        default=[],
        metavar="REPORT-ID=PATH",
        help="Override a known report artifact path; repeatable.",
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Require every core report artifact to be present.",
    )
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--check-freshness", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_cross_report_consistency_freshness(
            repo_root=ns.root,
            report_path=ns.out,
            report_json=ns.report_json,
            complete=ns.complete,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
            sys.stdout.write(f"mode={freshness['mode']}\n")
        return 0 if freshness["fresh"] else 1

    payload = write_cross_report_consistency(
        repo_root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        report_json=ns.report_json,
        complete=ns.complete,
    )
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            "\n".join(
                [
                    f"consistency_status={payload['consistency_status']}",
                    f"mode={payload['mode']}",
                    f"blocking_findings={payload['finding_counts']['blocking']}",
                    f"partial_findings={payload['finding_counts']['partial']}",
                    f"advisory_findings={payload['finding_counts']['advisory']}",
                    "reporting_only=true",
                    "repo_mutation=false",
                    "automation_allowed=false",
                    "patch_application_allowed=false",
                    "security_dismissal_allowed=false",
                    "merge_authorized=false",
                    "semantic_equivalence_proven=false",
                ]
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
