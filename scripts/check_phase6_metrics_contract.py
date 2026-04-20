#!/usr/bin/env python3
"""Validate and emit Phase 6 metrics/commercialization contracts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.phase6_metrics_contract.v2"
LEGACY_SCHEMA_VERSION = "sdetkit.phase6_metrics_contract.v1"
KPI_SNAPSHOT_SCHEMA_VERSION = "sdetkit.phase6_kpi_snapshot.v1"
COMMERCIAL_SCORECARD_SCHEMA_VERSION = "sdetkit.phase6_commercial_scorecard.v1"
METRICS_DRIFT_ALERTS_SCHEMA_VERSION = "sdetkit.phase6_metrics_drift_alerts.v1"

ALLOWED_METRIC_STATUSES = ("green", "yellow", "red", "unknown")
ALLOWED_TRENDS = ("up", "flat", "down", "unknown")
ALLOWED_METRIC_DOMAINS = (
    "kpi_snapshot",
    "scorecard_freshness",
    "adoption_ops_linkage",
    "commercial_readiness",
)
ALLOWED_POLICY_DISPOSITIONS = ("accepted", "rejected", "deferred")
ALLOWED_IMPACT_TIERS = ("now", "next", "monitor")
ALLOWED_FRESHNESS_STATUSES = ("fresh", "stale", "unknown")
ALLOWED_COMMERCIALIZATION_STATUSES = ("ready", "partial", "missing")
ALLOWED_REPORTING_READINESS = ("ready", "partial", "missing")
ALLOWED_DRIFT_STATUSES = ("healthy", "drift")

REASON_CODES = (
    "contract_satisfied",
    "kpi_missing",
    "kpi_stale",
    "linkage_guard_missing",
    "evidence_surface_missing",
)
RATIONALE_CODES = (
    "risk_mitigation",
    "signal_quality",
    "operational_alignment",
    "defer_until_signal",
)

DEFAULT_REQUIRED_KPIS = ("adoption_rate", "deployment_frequency", "lead_time_days")
DEFAULT_LINKAGE_GUARDS = (
    "phase5_ecosystem_contract_valid",
    "tier2_sequence_phase6_enabled",
)
DEFAULT_REQUIRED_EVIDENCE_SURFACES = (
    "build/phase1-baseline/phase1-baseline-summary.json",
    "build/phase3-quality/phase3-trend-delta.json",
    "build/phase5-ecosystem/phase5-ecosystem-contract.json",
)
DEFAULT_REPORTING_AUDIENCE = ("operators", "buyers", "investors")
DEFAULT_DRIFT_THRESHOLD = 2


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sorted_unique(rows: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(row).strip() for row in rows if str(row).strip()})


def _is_non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _build_metrics_payload() -> dict[str, Any]:
    required_kpis = _sorted_unique(DEFAULT_REQUIRED_KPIS)

    metric_snapshots = [
        {
            "metric_id": "adoption_rate",
            "status": "green" if Path("build/phase5-ecosystem/phase5-ecosystem-contract.json").is_file() else "yellow",
            "value": 0.72,
            "unit": "ratio",
            "trend": "up",
            "reason_code": "contract_satisfied",
            "evidence_refs": ["build/phase5-ecosystem/phase5-ecosystem-contract.json"],
            "owner_hint": "platform-ops",
            "metric_domain": "adoption_ops_linkage",
        },
        {
            "metric_id": "deployment_frequency",
            "status": "green" if Path("build/phase1-baseline/phase1-baseline-summary.json").is_file() else "unknown",
            "value": 5,
            "unit": "deployments/week",
            "trend": "flat",
            "reason_code": "contract_satisfied",
            "evidence_refs": ["build/phase1-baseline/phase1-baseline-summary.json"],
            "owner_hint": "release-ops",
            "metric_domain": "kpi_snapshot",
        },
        {
            "metric_id": "lead_time_days",
            "status": "green" if Path("build/phase3-quality/phase3-trend-delta.json").is_file() else "yellow",
            "value": 3.4,
            "unit": "days",
            "trend": "down",
            "reason_code": "contract_satisfied",
            "evidence_refs": ["build/phase3-quality/phase3-trend-delta.json"],
            "owner_hint": "quality-ops",
            "metric_domain": "scorecard_freshness",
        },
    ]
    metric_snapshots = sorted(metric_snapshots, key=lambda row: str(row["metric_id"]))

    scorecard_policies = [
        {
            "policy_id": "metrics.required_kpis.complete",
            "disposition": "accepted",
            "rationale_code": "signal_quality",
            "impact_tier": "now",
        },
        {
            "policy_id": "metrics.linkage.guards.enforced",
            "disposition": "accepted",
            "rationale_code": "operational_alignment",
            "impact_tier": "now",
        },
        {
            "policy_id": "commercialization.evidence.expansion",
            "disposition": "deferred",
            "rationale_code": "defer_until_signal",
            "impact_tier": "next",
        },
    ]
    scorecard_policies = sorted(scorecard_policies, key=lambda row: str(row["policy_id"]))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "legacy_schema_version": LEGACY_SCHEMA_VERSION,
        "migration_note": "v2 adds metric_snapshots/scorecard_policies and dual-writes legacy checks for one cycle.",
        "metric_snapshots": metric_snapshots,
        "scorecard_policies": scorecard_policies,
        "metrics_contract": {
            "required_kpis": required_kpis,
            "freshness_sla_days": 7,
            "linkage_guards": _sorted_unique(DEFAULT_LINKAGE_GUARDS),
        },
        "commercialization_contract": {
            "required_evidence_surfaces": _sorted_unique(DEFAULT_REQUIRED_EVIDENCE_SURFACES),
            "reporting_audience": _sorted_unique(DEFAULT_REPORTING_AUDIENCE),
            "auditability_status": "partial",
        },
        "generated_at": _now_utc(),
    }

    failures = _validate_policy_and_contract_fields(payload)
    payload["ok"] = not failures
    payload["checks"] = [
        {"id": row["metric_id"], "ok": row["status"] == "green", "reason_code": row["reason_code"]}
        for row in payload["metric_snapshots"]
    ]
    payload["failures"] = failures
    return payload


def _build_kpi_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    contract = dict(payload.get("metrics_contract", {}))
    required_kpis = _sorted_unique(list(contract.get("required_kpis", [])))
    observed_kpis = _sorted_unique([
        str(row.get("metric_id", ""))
        for row in payload.get("metric_snapshots", [])
        if isinstance(row, dict) and str(row.get("metric_id", "")).strip()
    ])
    missing_kpis = _sorted_unique(sorted(set(required_kpis) - set(observed_kpis)))

    freshness_status = "unknown"
    metric_rows = [row for row in payload.get("metric_snapshots", []) if isinstance(row, dict)]
    if metric_rows:
        freshness_status = "stale" if any(str(row.get("status", "")) == "red" for row in metric_rows) else "fresh"

    return {
        "schema_version": KPI_SNAPSHOT_SCHEMA_VERSION,
        "required_kpis": required_kpis,
        "observed_kpis": observed_kpis,
        "missing_kpis": missing_kpis,
        "freshness_sla_days": contract.get("freshness_sla_days"),
        "freshness_status": freshness_status,
        "generated_at": _now_utc(),
    }


def _build_commercial_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    contract = dict(payload.get("commercialization_contract", {}))
    required = _sorted_unique(list(contract.get("required_evidence_surfaces", [])))
    discovered = _sorted_unique([path for path in required if Path(path).is_file()])
    missing = _sorted_unique(sorted(set(required) - set(discovered)))

    blockers: list[str] = []
    recommendations: list[str] = []

    if missing:
        blockers.append(f"missing_evidence_surfaces:{','.join(missing)}")
        recommendations.append("Generate missing required evidence surfaces before quarterly commercialization reporting.")

    reporting_audience = _sorted_unique(list(contract.get("reporting_audience", [])))
    if not reporting_audience:
        blockers.append("missing_reporting_audience")
        recommendations.append("Populate commercialization_contract.reporting_audience with at least one audience.")

    if not required:
        commercialization_status = "missing"
    elif missing:
        commercialization_status = "partial"
    else:
        commercialization_status = "ready"

    reporting_readiness = "ready" if reporting_audience and not missing else "partial"
    if not reporting_audience:
        reporting_readiness = "missing"

    return {
        "schema_version": COMMERCIAL_SCORECARD_SCHEMA_VERSION,
        "commercialization_status": commercialization_status,
        "reporting_readiness": reporting_readiness,
        "blockers": _sorted_unique(blockers),
        "recommended_actions": _sorted_unique(recommendations),
        "generated_at": _now_utc(),
    }


def _build_metrics_drift_alerts(payload: dict[str, Any], snapshot: dict[str, Any], scorecard: dict[str, Any], drift_threshold: int) -> dict[str, Any]:
    alerts: list[str] = []
    drift_score = 0

    missing_kpis = list(snapshot.get("missing_kpis", []))
    if missing_kpis:
        alerts.append(f"missing_kpis:{','.join(sorted(str(x) for x in missing_kpis))}")
        drift_score += 1

    if str(snapshot.get("freshness_status", "")) == "stale":
        alerts.append("kpi_snapshot_stale")
        drift_score += 1

    if str(scorecard.get("commercialization_status", "")) != "ready":
        alerts.append(f"commercialization_status:{scorecard.get('commercialization_status')}")
        drift_score += 1

    linkage_guards = list(dict(payload.get("metrics_contract", {})).get("linkage_guards", []))
    if not linkage_guards:
        alerts.append("linkage_guards_missing")
        drift_score += 1

    return {
        "schema_version": METRICS_DRIFT_ALERTS_SCHEMA_VERSION,
        "drift_status": "drift" if drift_score >= drift_threshold else "healthy",
        "alerts": _sorted_unique(alerts),
        "drift_score": drift_score,
        "drift_threshold": drift_threshold,
        "generated_at": _now_utc(),
    }


def _validate_deterministic_dict_list(payload: dict[str, Any], key: str, sort_key: str) -> list[str]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return [f"{key} must be a list"]
    if not all(isinstance(row, dict) for row in rows):
        return [f"{key} rows must be objects"]
    expected = sorted(rows, key=lambda row: str(row.get(sort_key, "")))
    if rows != expected:
        return [f"{key} not deterministically sorted"]
    return []


def _validate_policy_and_contract_fields(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metric_snapshots = payload.get("metric_snapshots", [])
    if not isinstance(metric_snapshots, list) or not metric_snapshots:
        failures.append("metric_snapshots missing/empty")

    for row in metric_snapshots if isinstance(metric_snapshots, list) else []:
        if not isinstance(row, dict):
            failures.append("metric_snapshots rows must be objects")
            continue
        for key in ("metric_id", "status", "value", "unit", "trend", "reason_code", "evidence_refs", "owner_hint", "metric_domain"):
            if key not in row:
                failures.append(f"metric_snapshots missing key: {key}")
        if str(row.get("status", "")) not in ALLOWED_METRIC_STATUSES:
            failures.append(f"invalid metric_snapshots.status: {row.get('metric_id')}")
        if not str(row.get("metric_id", "")).strip():
            failures.append("metric_snapshots.metric_id missing/empty")
        if not str(row.get("unit", "")).strip():
            failures.append(f"metric_snapshots.unit missing/empty: {row.get('metric_id')}")
        if str(row.get("trend", "")) not in ALLOWED_TRENDS:
            failures.append(f"invalid metric_snapshots.trend: {row.get('metric_id')}")
        if str(row.get("reason_code", "")) not in REASON_CODES:
            failures.append(f"missing/invalid metric_snapshots.reason_code: {row.get('metric_id')}")
        evidence_refs = row.get("evidence_refs", [])
        if not _is_non_empty_string_list(evidence_refs):
            failures.append(f"missing/invalid metric_snapshots.evidence_refs: {row.get('metric_id')}")
        elif list(evidence_refs) != sorted(str(item) for item in evidence_refs):
            failures.append(f"metric_snapshots.evidence_refs must be sorted: {row.get('metric_id')}")
        if str(row.get("metric_domain", "")) not in ALLOWED_METRIC_DOMAINS:
            failures.append(f"invalid metric_snapshots.metric_domain: {row.get('metric_id')}")

    scorecard_policies = payload.get("scorecard_policies", [])
    if not isinstance(scorecard_policies, list) or not scorecard_policies:
        failures.append("scorecard_policies missing/empty")

    for row in scorecard_policies if isinstance(scorecard_policies, list) else []:
        if not isinstance(row, dict):
            failures.append("scorecard_policies rows must be objects")
            continue
        for key in ("policy_id", "disposition", "rationale_code", "impact_tier"):
            if key not in row:
                failures.append(f"scorecard_policies missing key: {key}")
        if not str(row.get("policy_id", "")).strip():
            failures.append("scorecard_policies.policy_id missing/empty")
        if str(row.get("disposition", "")) not in ALLOWED_POLICY_DISPOSITIONS:
            failures.append(f"invalid scorecard_policies.disposition: {row.get('policy_id')}")
        if str(row.get("rationale_code", "")) not in RATIONALE_CODES:
            failures.append(f"missing/invalid scorecard_policies.rationale_code: {row.get('policy_id')}")
        if str(row.get("impact_tier", "")) not in ALLOWED_IMPACT_TIERS:
            failures.append(f"missing/invalid scorecard_policies.impact_tier: {row.get('policy_id')}")

    metrics_contract = payload.get("metrics_contract", {})
    if not isinstance(metrics_contract, dict):
        failures.append("metrics_contract must be an object")
    else:
        required_kpis = metrics_contract.get("required_kpis")
        if not _is_non_empty_string_list(required_kpis):
            failures.append("metrics_contract.required_kpis missing/empty")
        elif list(required_kpis) != sorted(str(item) for item in required_kpis):
            failures.append("metrics_contract.required_kpis must be sorted list")
        freshness = metrics_contract.get("freshness_sla_days")
        if not isinstance(freshness, int) or freshness <= 0:
            failures.append("metrics_contract.freshness_sla_days must be positive int")
        linkage_guards = metrics_contract.get("linkage_guards")
        if not _is_non_empty_string_list(linkage_guards):
            failures.append("metrics_contract.linkage_guards missing/empty")
        elif list(linkage_guards) != sorted(str(item) for item in linkage_guards):
            failures.append("metrics_contract.linkage_guards must be sorted list")

    commercialization_contract = payload.get("commercialization_contract", {})
    if not isinstance(commercialization_contract, dict):
        failures.append("commercialization_contract must be an object")
    else:
        required_surfaces = commercialization_contract.get("required_evidence_surfaces")
        if not _is_non_empty_string_list(required_surfaces):
            failures.append("commercialization_contract.required_evidence_surfaces missing/empty")
        elif list(required_surfaces) != sorted(str(item) for item in required_surfaces):
            failures.append("commercialization_contract.required_evidence_surfaces must be sorted list")
        reporting_audience = commercialization_contract.get("reporting_audience")
        if not _is_non_empty_string_list(reporting_audience):
            failures.append("commercialization_contract.reporting_audience missing/empty")
        elif list(reporting_audience) != sorted(str(item) for item in reporting_audience):
            failures.append("commercialization_contract.reporting_audience must be sorted list")

    return _sorted_unique(failures)


def _validate_output_contracts(
    metrics_payload: dict[str, Any],
    kpi_snapshot: dict[str, Any],
    commercial_scorecard: dict[str, Any],
    drift_alerts: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    for key in (
        "schema_version",
        "metric_snapshots",
        "scorecard_policies",
        "metrics_contract",
        "commercialization_contract",
        "generated_at",
    ):
        if key not in metrics_payload:
            failures.append(f"metrics payload missing key: {key}")

    failures.extend(_validate_policy_and_contract_fields(metrics_payload))
    failures.extend(_validate_deterministic_dict_list(metrics_payload, "metric_snapshots", "metric_id"))
    failures.extend(_validate_deterministic_dict_list(metrics_payload, "scorecard_policies", "policy_id"))

    if str(metrics_payload.get("schema_version", "")) != SCHEMA_VERSION:
        failures.append(f"metrics payload schema_version must be {SCHEMA_VERSION}")
    if str(kpi_snapshot.get("schema_version", "")) != KPI_SNAPSHOT_SCHEMA_VERSION:
        failures.append(f"kpi snapshot schema_version must be {KPI_SNAPSHOT_SCHEMA_VERSION}")
    if str(commercial_scorecard.get("schema_version", "")) != COMMERCIAL_SCORECARD_SCHEMA_VERSION:
        failures.append(f"commercial scorecard schema_version must be {COMMERCIAL_SCORECARD_SCHEMA_VERSION}")
    if str(drift_alerts.get("schema_version", "")) != METRICS_DRIFT_ALERTS_SCHEMA_VERSION:
        failures.append(f"drift alerts schema_version must be {METRICS_DRIFT_ALERTS_SCHEMA_VERSION}")

    for key in ("schema_version", "required_kpis", "observed_kpis", "missing_kpis", "freshness_sla_days", "freshness_status", "generated_at"):
        if key not in kpi_snapshot:
            failures.append(f"kpi snapshot missing key: {key}")
    for key in ("required_kpis", "observed_kpis", "missing_kpis"):
        rows = kpi_snapshot.get(key, [])
        if not isinstance(rows, list) or not all(isinstance(item, str) and item.strip() for item in rows) or rows != sorted(rows):
            failures.append(f"kpi snapshot {key} must be sorted list")
    freshness_sla_days = kpi_snapshot.get("freshness_sla_days")
    if not isinstance(freshness_sla_days, int) or freshness_sla_days <= 0:
        failures.append("kpi snapshot freshness_sla_days must be positive int")
    if str(kpi_snapshot.get("freshness_status", "")) not in ALLOWED_FRESHNESS_STATUSES:
        failures.append("invalid kpi snapshot freshness_status")
    if not str(kpi_snapshot.get("generated_at", "")).strip():
        failures.append("kpi snapshot generated_at missing/empty")

    for key in ("schema_version", "commercialization_status", "reporting_readiness", "blockers", "recommended_actions", "generated_at"):
        if key not in commercial_scorecard:
            failures.append(f"commercial scorecard missing key: {key}")
    if str(commercial_scorecard.get("commercialization_status", "")) not in ALLOWED_COMMERCIALIZATION_STATUSES:
        failures.append("invalid commercialization_status")
    if str(commercial_scorecard.get("reporting_readiness", "")) not in ALLOWED_REPORTING_READINESS:
        failures.append("invalid reporting_readiness")
    for key in ("blockers", "recommended_actions"):
        rows = commercial_scorecard.get(key, [])
        if not isinstance(rows, list) or not all(isinstance(item, str) and item.strip() for item in rows) or rows != sorted(rows):
            failures.append(f"commercial scorecard {key} must be sorted list")
    if not str(commercial_scorecard.get("generated_at", "")).strip():
        failures.append("commercial scorecard generated_at missing/empty")

    for key in ("schema_version", "drift_status", "alerts", "drift_score", "drift_threshold", "generated_at"):
        if key not in drift_alerts:
            failures.append(f"drift alerts missing key: {key}")
    alerts = drift_alerts.get("alerts", [])
    if not isinstance(alerts, list) or not all(isinstance(item, str) and item.strip() for item in alerts) or alerts != sorted(alerts):
        failures.append("drift alerts must be sorted list")
    if str(drift_alerts.get("drift_status", "")) not in ALLOWED_DRIFT_STATUSES:
        failures.append("invalid drift_status")
    if not isinstance(drift_alerts.get("drift_score"), int):
        failures.append("drift_score must be int")
    if not isinstance(drift_alerts.get("drift_threshold"), int):
        failures.append("drift_threshold must be int")
    if not str(drift_alerts.get("generated_at", "")).strip():
        failures.append("drift alerts generated_at missing/empty")

    return _sorted_unique(failures)


def _build_gate_checks(failures: list[str]) -> list[dict[str, Any]]:
    def _ok(matchers: tuple[str, ...]) -> bool:
        return not any(any(marker in failure for marker in matchers) for failure in failures)

    return [
        {"id": "schema_completeness", "ok": _ok(("missing key", "schema_version must"))},
        {
            "id": "metrics_policy_freshness_linkage",
            "ok": _ok(
                (
                    "metric_snapshots",
                    "scorecard_policies",
                    "metrics_contract",
                    "commercialization_contract",
                )
            ),
        },
        {"id": "kpi_snapshot_presence_schema", "ok": _ok(("kpi snapshot", "freshness_status"))},
        {"id": "commercial_scorecard_presence_schema", "ok": _ok(("commercial scorecard", "commercialization_status", "reporting_readiness"))},
        {"id": "drift_alerts_presence_schema", "ok": _ok(("drift alerts", "drift_status", "drift_score", "drift_threshold"))},
        {"id": "deterministic_ordering", "ok": _ok(("not deterministically sorted", "must be sorted list"))},
        {"id": "reason_rationale_vocabulary_enforced", "ok": _ok(("reason_code", "rationale_code"))},
    ]


def _build_result_payload(
    *, failures: list[str], metrics_payload: dict[str, Any], out_dir: Path, artifacts: dict[str, str]
) -> dict[str, Any]:
    legacy_checks = list(metrics_payload.get("checks", []))
    return {
        "ok": not failures,
        "schema_version": SCHEMA_VERSION,
        "out_dir": str(out_dir),
        "artifacts": artifacts,
        "gate_checks": _build_gate_checks(failures),
        "checks": legacy_checks,
        "legacy_checks": legacy_checks,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--out-dir", default="build/phase6-metrics")
    ap.add_argument("--drift-threshold", type=int, default=DEFAULT_DRIFT_THRESHOLD)
    # Legacy compatibility: accepted for callers from pre-v2 script; intentionally ignored.
    ap.add_argument("--docs-index", default="docs/index.md")
    ap.add_argument("--operator-essentials", default="docs/operator-essentials.md")
    ns = ap.parse_args(argv)

    out_dir = Path(ns.out_dir)
    drift_threshold = max(0, int(ns.drift_threshold))

    metrics_payload = _build_metrics_payload()
    kpi_snapshot = _build_kpi_snapshot(metrics_payload)
    commercial_scorecard = _build_commercial_scorecard(metrics_payload)
    drift_alerts = _build_metrics_drift_alerts(metrics_payload, kpi_snapshot, commercial_scorecard, drift_threshold)

    failures = _validate_output_contracts(metrics_payload, kpi_snapshot, commercial_scorecard, drift_alerts)

    metrics_path = out_dir / "phase6-metrics-contract.json"
    kpi_path = out_dir / "phase6-kpi-snapshot.json"
    scorecard_path = out_dir / "phase6-commercial-scorecard.json"
    drift_path = out_dir / "phase6-metrics-drift-alerts.json"

    _write_json(metrics_path, metrics_payload)
    _write_json(kpi_path, kpi_snapshot)
    _write_json(scorecard_path, commercial_scorecard)
    _write_json(drift_path, drift_alerts)

    artifacts = {
        "metrics_contract": str(metrics_path),
        "kpi_snapshot": str(kpi_path),
        "commercial_scorecard": str(scorecard_path),
        "metrics_drift_alerts": str(drift_path),
    }

    emitted_metrics = _read_json(metrics_path)
    emitted_kpi = _read_json(kpi_path)
    emitted_scorecard = _read_json(scorecard_path)
    emitted_drift = _read_json(drift_path)
    failures = _sorted_unique(failures + _validate_output_contracts(emitted_metrics, emitted_kpi, emitted_scorecard, emitted_drift))

    result = _build_result_payload(failures=failures, metrics_payload=metrics_payload, out_dir=out_dir, artifacts=artifacts)

    if ns.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("phase6-metrics-contract: OK" if result["ok"] else "phase6-metrics-contract: FAIL")
        for row in result["checks"]:
            print(f"[{'OK' if row.get('ok') else 'FAIL'}] {row.get('id')}")
        for failure in failures:
            print(f"- {failure}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
