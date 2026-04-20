#!/usr/bin/env python3
"""Validate and emit Phase 5 ecosystem/platform scaling contracts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.phase5_ecosystem_contract.v2"
LEGACY_SCHEMA_VERSION = "sdetkit.phase5_ecosystem_contract.v1"
PARTNER_PACKAGING_SCHEMA_VERSION = "sdetkit.phase5_partner_packaging.v1"
RELIABILITY_SCHEMA_VERSION = "sdetkit.phase5_ecosystem_reliability.v1"
DRIFT_ALERTS_SCHEMA_VERSION = "sdetkit.phase5_ecosystem_drift_alerts.v1"

ALLOWED_CHECK_STATUSES = ("pass", "warn", "fail")
ALLOWED_ECOSYSTEM_DOMAINS = (
    "plugin_reliability",
    "integration_playbook",
    "certification",
    "partner_packaging",
    "portfolio_scorecards",
)
ALLOWED_DISPOSITIONS = ("accepted", "rejected", "deferred")
ALLOWED_IMPACT_TIERS = ("now", "next", "monitor")
ALLOWED_PACKAGING_STATUSES = ("complete", "incomplete")
ALLOWED_PLUGIN_RELIABILITY_STATUSES = ("stable", "degraded", "unknown")
ALLOWED_INTEGRATION_PLAYBOOK_STATUSES = ("ready", "partial", "missing")
ALLOWED_CERTIFICATION_READINESS = ("ready", "partial", "missing")
ALLOWED_DRIFT_STATUSES = ("healthy", "drift")

REASON_CODES = (
    "contract_satisfied",
    "missing_required_reference",
    "diagnostics_missing",
    "integration_gap",
    "packaging_incomplete",
)
RATIONALE_CODES = (
    "risk_mitigation",
    "compatibility_commitment",
    "partner_enablement",
    "defer_until_signal",
)

REQUIRED_PARTNER_ARTIFACTS = (
    "docs/integrations-and-extension-boundary.md",
    "docs/operator-essentials.md",
    "pyproject.toml",
)
DEFAULT_SUPPORT_SURFACE = (
    "make phase5-ecosystem-contract",
    "python scripts/check_phase5_ecosystem_contract.py --format json",
)
DRIFT_THRESHOLD = 2


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sorted_unique(rows: list[str]) -> list[str]:
    return sorted({str(row).strip() for row in rows if str(row).strip()})


def _is_non_empty_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _build_ecosystem_payload() -> dict[str, Any]:
    check_specs = [
        ("certification.criteria", "certification", "docs/integrations-and-extension-boundary.md"),
        (
            "integration.playbook",
            "integration_playbook",
            "docs/integrations-and-extension-boundary.md",
        ),
        ("partner.packaging.surface", "partner_packaging", "docs/operator-essentials.md"),
        ("plugin.runtime.boundary", "plugin_reliability", "src/sdetkit/plugin_system.py"),
        ("portfolio.scorecards.source", "portfolio_scorecards", "docs/operator-essentials.md"),
    ]

    ecosystem_checks: list[dict[str, Any]] = []
    for check_id, domain, evidence in check_specs:
        found = Path(evidence).is_file()
        ecosystem_checks.append(
            {
                "check_id": check_id,
                "status": "pass" if found else "fail",
                "reason_code": "contract_satisfied" if found else "missing_required_reference",
                "evidence_refs": [evidence],
                "owner_hint": "ecosystem-ops",
                "ecosystem_domain": domain,
            }
        )
    ecosystem_checks.sort(key=lambda row: str(row["check_id"]))

    extension_policy = [
        {
            "policy_id": "extension.compatibility.versioned",
            "disposition": "accepted",
            "rationale_code": "compatibility_commitment",
            "impact_tier": "now",
        },
        {
            "policy_id": "extension.failure.isolation",
            "disposition": "accepted",
            "rationale_code": "risk_mitigation",
            "impact_tier": "now",
        },
        {
            "policy_id": "ecosystem.certification.expansion",
            "disposition": "deferred",
            "rationale_code": "defer_until_signal",
            "impact_tier": "next",
        },
    ]
    extension_policy.sort(key=lambda row: str(row["policy_id"]))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "legacy_schema_version": LEGACY_SCHEMA_VERSION,
        "migration_note": "v2 adds ecosystem_checks/extension_policy and dual-writes legacy checks for one cycle.",
        "ecosystem_checks": ecosystem_checks,
        "extension_policy": extension_policy,
        "plugin_reliability_contract": {
            "supported_extension_modes": _sorted_unique(["entry_points", "runtime_registry"]),
            "failure_isolation_guards": _sorted_unique(
                [
                    "plugin load errors stay non-blocking by default",
                    "per-plugin timeout and exception boundaries",
                ]
            ),
            "compatibility_guards": _sorted_unique(
                [
                    "make phase4-governance-contract",
                    "make phase5-ecosystem-contract",
                ]
            ),
        },
        "partner_packaging_contract": {
            "required_artifacts": _sorted_unique(list(REQUIRED_PARTNER_ARTIFACTS)),
            "support_surface": _sorted_unique(list(DEFAULT_SUPPORT_SURFACE)),
            "auditability_status": "pass",
        },
        "generated_at": _now_utc(),
    }

    failures = _validate_policy_and_compatibility(payload)
    payload["ok"] = not failures
    payload["checks"] = [
        {
            "id": row["check_id"],
            "ok": row["status"] == "pass",
            "reason_code": row["reason_code"],
        }
        for row in payload["ecosystem_checks"]
    ]
    payload["failures"] = failures
    return payload


def _build_partner_packaging(payload: dict[str, Any]) -> dict[str, Any]:
    contract = dict(payload.get("partner_packaging_contract", {}))
    required = _sorted_unique(list(contract.get("required_artifacts", [])))
    discovered = _sorted_unique([path for path in required if Path(path).is_file()])
    missing = _sorted_unique(sorted(set(required) - set(discovered)))
    support_surface = _sorted_unique(list(contract.get("support_surface", [])))
    packaging_status = "complete" if not missing else "incomplete"

    return {
        "schema_version": PARTNER_PACKAGING_SCHEMA_VERSION,
        "required_artifacts": required,
        "discovered_artifacts": discovered,
        "missing_artifacts": missing,
        "support_surface": support_surface,
        "packaging_status": packaging_status,
        "generated_at": _now_utc(),
    }


def _build_reliability(payload: dict[str, Any]) -> dict[str, Any]:
    plugin_contract = dict(payload.get("plugin_reliability_contract", {}))
    checks = list(payload.get("ecosystem_checks", []))

    blockers: list[str] = []
    recommended_actions: list[str] = []

    failure_isolation_guards = _sorted_unique(
        list(plugin_contract.get("failure_isolation_guards", []))
    )
    compatibility_guards = _sorted_unique(list(plugin_contract.get("compatibility_guards", [])))

    if not failure_isolation_guards or not compatibility_guards:
        blockers.append("extension_diagnostics_missing")
        recommended_actions.append(
            "Populate failure_isolation_guards and compatibility_guards in plugin_reliability_contract."
        )

    integration_status = "ready"
    certification_status = "ready"
    for row in checks:
        if not isinstance(row, dict):
            continue
        domain = str(row.get("ecosystem_domain", ""))
        status = str(row.get("status", ""))
        if domain == "integration_playbook" and status != "pass":
            integration_status = "partial"
            blockers.append("integration_playbook_check_failed")
            recommended_actions.append(
                "Update integration playbook evidence and rerun phase5 contract gate."
            )
        if domain == "certification" and status != "pass":
            certification_status = "partial"
            blockers.append("certification_check_failed")
            recommended_actions.append("Publish certification criteria evidence for extensions.")

    plugin_status = "stable"
    if blockers:
        plugin_status = "degraded"
    elif not checks:
        plugin_status = "unknown"

    return {
        "schema_version": RELIABILITY_SCHEMA_VERSION,
        "plugin_reliability_status": plugin_status,
        "integration_playbook_status": integration_status,
        "certification_readiness": certification_status,
        "blockers": _sorted_unique(blockers),
        "recommended_actions": _sorted_unique(recommended_actions),
        "generated_at": _now_utc(),
    }


def _build_drift_alerts(
    ecosystem_payload: dict[str, Any], packaging: dict[str, Any], reliability: dict[str, Any]
) -> dict[str, Any]:
    alerts: list[str] = []
    drift_score = 0

    failed_checks = [
        str(row.get("check_id", ""))
        for row in ecosystem_payload.get("ecosystem_checks", [])
        if isinstance(row, dict) and str(row.get("status", "")) != "pass"
    ]
    if failed_checks:
        alerts.append(f"ecosystem_check_failures:{','.join(sorted(failed_checks))}")
        drift_score += 1

    missing_artifacts = list(packaging.get("missing_artifacts", []))
    if missing_artifacts:
        alerts.append(
            f"partner_packaging_missing:{','.join(sorted(str(x) for x in missing_artifacts))}"
        )
        drift_score += 1

    reliability_blockers = list(reliability.get("blockers", []))
    if reliability_blockers:
        alerts.append(
            f"reliability_blockers:{','.join(sorted(str(x) for x in reliability_blockers))}"
        )
        drift_score += 1

    return {
        "schema_version": DRIFT_ALERTS_SCHEMA_VERSION,
        "drift_status": "drift" if drift_score >= DRIFT_THRESHOLD else "healthy",
        "alerts": _sorted_unique(alerts),
        "drift_score": drift_score,
        "drift_threshold": DRIFT_THRESHOLD,
        "generated_at": _now_utc(),
    }


def _validate_deterministic_dict_list(
    payload: dict[str, Any], key: str, sort_key: str
) -> list[str]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        return [f"{key} must be a list"]
    if not all(isinstance(row, dict) for row in rows):
        return [f"{key} rows must be objects"]
    expected = sorted(rows, key=lambda row: str(row.get(sort_key, "")))
    if rows != expected:
        return [f"{key} not deterministically sorted"]
    return []


def _validate_policy_and_compatibility(ecosystem_payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    for row in ecosystem_payload.get("ecosystem_checks", []):
        if not isinstance(row, dict):
            failures.append("ecosystem_checks rows must be objects")
            continue
        if str(row.get("status", "")) not in ALLOWED_CHECK_STATUSES:
            failures.append(f"invalid ecosystem_checks.status: {row.get('check_id')}")
        if str(row.get("reason_code", "")) not in REASON_CODES:
            failures.append(f"missing/invalid ecosystem_checks.reason_code: {row.get('check_id')}")
        evidence = row.get("evidence_refs", [])
        if not isinstance(evidence, list) or not evidence:
            failures.append(f"missing ecosystem_checks.evidence_refs: {row.get('check_id')}")
        if str(row.get("ecosystem_domain", "")) not in ALLOWED_ECOSYSTEM_DOMAINS:
            failures.append(f"invalid ecosystem_checks.ecosystem_domain: {row.get('check_id')}")

    for row in ecosystem_payload.get("extension_policy", []):
        if not isinstance(row, dict):
            failures.append("extension_policy rows must be objects")
            continue
        if str(row.get("disposition", "")) not in ALLOWED_DISPOSITIONS:
            failures.append(f"invalid extension_policy.disposition: {row.get('policy_id')}")
        if str(row.get("rationale_code", "")) not in RATIONALE_CODES:
            failures.append(
                f"missing/invalid extension_policy.rationale_code: {row.get('policy_id')}"
            )
        if str(row.get("impact_tier", "")) not in ALLOWED_IMPACT_TIERS:
            failures.append(f"missing/invalid extension_policy.impact_tier: {row.get('policy_id')}")

    plugin_contract = ecosystem_payload.get("plugin_reliability_contract", {})
    if not isinstance(plugin_contract, dict):
        failures.append("plugin_reliability_contract must be an object")
    else:
        if not _is_non_empty_string_list(plugin_contract.get("failure_isolation_guards")):
            failures.append("plugin_reliability_contract.failure_isolation_guards missing/empty")
        if not _is_non_empty_string_list(plugin_contract.get("compatibility_guards")):
            failures.append("plugin_reliability_contract.compatibility_guards missing/empty")

    packaging_contract = ecosystem_payload.get("partner_packaging_contract", {})
    if not isinstance(packaging_contract, dict):
        failures.append("partner_packaging_contract must be an object")
    else:
        if not _is_non_empty_string_list(packaging_contract.get("required_artifacts")):
            failures.append("partner_packaging_contract.required_artifacts missing/empty")
        if not _is_non_empty_string_list(packaging_contract.get("support_surface")):
            failures.append("partner_packaging_contract.support_surface missing/empty")

    return _sorted_unique(failures)


def _validate_output_contracts(
    ecosystem_payload: dict[str, Any],
    packaging_payload: dict[str, Any],
    reliability_payload: dict[str, Any],
    drift_payload: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    if str(ecosystem_payload.get("schema_version", "")) != SCHEMA_VERSION:
        failures.append(f"ecosystem payload schema_version must be {SCHEMA_VERSION}")
    if str(packaging_payload.get("schema_version", "")) != PARTNER_PACKAGING_SCHEMA_VERSION:
        failures.append(
            f"partner packaging schema_version must be {PARTNER_PACKAGING_SCHEMA_VERSION}"
        )
    if str(reliability_payload.get("schema_version", "")) != RELIABILITY_SCHEMA_VERSION:
        failures.append(f"reliability schema_version must be {RELIABILITY_SCHEMA_VERSION}")
    if str(drift_payload.get("schema_version", "")) != DRIFT_ALERTS_SCHEMA_VERSION:
        failures.append(f"drift schema_version must be {DRIFT_ALERTS_SCHEMA_VERSION}")

    for key in (
        "schema_version",
        "ecosystem_checks",
        "extension_policy",
        "plugin_reliability_contract",
        "partner_packaging_contract",
        "generated_at",
    ):
        if key not in ecosystem_payload:
            failures.append(f"ecosystem payload missing key: {key}")

    failures.extend(_validate_policy_and_compatibility(ecosystem_payload))
    failures.extend(
        _validate_deterministic_dict_list(ecosystem_payload, "ecosystem_checks", "check_id")
    )
    failures.extend(
        _validate_deterministic_dict_list(ecosystem_payload, "extension_policy", "policy_id")
    )

    for key in (
        "schema_version",
        "required_artifacts",
        "discovered_artifacts",
        "missing_artifacts",
        "support_surface",
        "packaging_status",
        "generated_at",
    ):
        if key not in packaging_payload:
            failures.append(f"partner packaging payload missing key: {key}")
    for list_key in (
        "required_artifacts",
        "discovered_artifacts",
        "missing_artifacts",
        "support_surface",
    ):
        rows = packaging_payload.get(list_key, [])
        if (
            not isinstance(rows, list)
            or not all(isinstance(item, str) and item.strip() for item in rows)
            or rows != sorted(rows)
        ):
            failures.append(f"partner packaging {list_key} must be sorted list")
    if str(packaging_payload.get("packaging_status", "")) not in ALLOWED_PACKAGING_STATUSES:
        failures.append(
            f"invalid partner packaging status: {packaging_payload.get('packaging_status')}"
        )

    for key in (
        "schema_version",
        "plugin_reliability_status",
        "integration_playbook_status",
        "certification_readiness",
        "blockers",
        "recommended_actions",
        "generated_at",
    ):
        if key not in reliability_payload:
            failures.append(f"reliability payload missing key: {key}")
    if (
        str(reliability_payload.get("plugin_reliability_status", ""))
        not in ALLOWED_PLUGIN_RELIABILITY_STATUSES
    ):
        failures.append("invalid plugin_reliability_status")
    if (
        str(reliability_payload.get("integration_playbook_status", ""))
        not in ALLOWED_INTEGRATION_PLAYBOOK_STATUSES
    ):
        failures.append("invalid integration_playbook_status")
    if (
        str(reliability_payload.get("certification_readiness", ""))
        not in ALLOWED_CERTIFICATION_READINESS
    ):
        failures.append("invalid certification_readiness")
    for list_key in ("blockers", "recommended_actions"):
        rows = reliability_payload.get(list_key, [])
        if (
            not isinstance(rows, list)
            or not all(isinstance(item, str) and item.strip() for item in rows)
            or rows != sorted(rows)
        ):
            failures.append(f"reliability {list_key} must be sorted list")

    for key in (
        "schema_version",
        "drift_status",
        "alerts",
        "drift_score",
        "drift_threshold",
        "generated_at",
    ):
        if key not in drift_payload:
            failures.append(f"drift payload missing key: {key}")
    alerts = drift_payload.get("alerts", [])
    if (
        not isinstance(alerts, list)
        or not all(isinstance(item, str) and item.strip() for item in alerts)
        or alerts != sorted(alerts)
    ):
        failures.append("drift alerts must be sorted list")
    if str(drift_payload.get("drift_status", "")) not in ALLOWED_DRIFT_STATUSES:
        failures.append("invalid drift_status")
    if not isinstance(drift_payload.get("drift_score"), int):
        failures.append("drift_score must be int")
    if not isinstance(drift_payload.get("drift_threshold"), int):
        failures.append("drift_threshold must be int")

    return _sorted_unique(failures)


def _build_gate_checks(failures: list[str]) -> list[dict[str, Any]]:
    def _ok(matchers: tuple[str, ...]) -> bool:
        return not any(any(marker in failure for marker in matchers) for failure in failures)

    return [
        {"id": "schema_completeness", "ok": _ok(("payload missing key", "schema_version must"))},
        {
            "id": "ecosystem_policy_compatibility",
            "ok": _ok(
                (
                    "plugin_reliability_contract",
                    "partner_packaging_contract",
                    "ecosystem_checks.",
                    "extension_policy.",
                )
            ),
        },
        {"id": "partner_packaging_presence_schema", "ok": _ok(("partner packaging",))},
        {
            "id": "reliability_presence_schema",
            "ok": _ok(
                (
                    "reliability ",
                    "plugin_reliability_status",
                    "integration_playbook_status",
                    "certification_readiness",
                )
            ),
        },
        {
            "id": "drift_alerts_presence_schema",
            "ok": _ok(("drift ", "drift_status", "drift_score", "drift_threshold")),
        },
        {
            "id": "deterministic_ordering",
            "ok": _ok(("not deterministically sorted", "must be sorted list")),
        },
        {
            "id": "reason_rationale_vocabulary_enforced",
            "ok": _ok(("reason_code", "rationale_code")),
        },
    ]


def _build_result_payload(
    *,
    failures: list[str],
    ecosystem_payload: dict[str, Any],
    out_dir: Path,
    artifacts: dict[str, str],
) -> dict[str, Any]:
    gate_checks = _build_gate_checks(failures)
    legacy_checks = list(ecosystem_payload.get("checks", []))
    return {
        "ok": not failures,
        "schema_version": SCHEMA_VERSION,
        "out_dir": str(out_dir),
        "artifacts": artifacts,
        "gate_checks": gate_checks,
        # legacy bridge: keep historical checks shape for one-cycle compatibility
        "checks": legacy_checks,
        "legacy_checks": legacy_checks,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--out-dir", default="build/phase5-ecosystem")
    ns = ap.parse_args(argv)

    out_dir = Path(ns.out_dir)

    ecosystem_payload = _build_ecosystem_payload()
    partner_packaging_payload = _build_partner_packaging(ecosystem_payload)
    reliability_payload = _build_reliability(ecosystem_payload)
    drift_payload = _build_drift_alerts(
        ecosystem_payload, partner_packaging_payload, reliability_payload
    )

    failures = _validate_output_contracts(
        ecosystem_payload,
        partner_packaging_payload,
        reliability_payload,
        drift_payload,
    )

    ecosystem_path = out_dir / "phase5-ecosystem-contract.json"
    packaging_path = out_dir / "phase5-partner-packaging.json"
    reliability_path = out_dir / "phase5-ecosystem-reliability.json"
    drift_path = out_dir / "phase5-ecosystem-drift-alerts.json"

    _write_json(ecosystem_path, ecosystem_payload)
    _write_json(packaging_path, partner_packaging_payload)
    _write_json(reliability_path, reliability_payload)
    _write_json(drift_path, drift_payload)

    artifacts = {
        "ecosystem_contract": str(ecosystem_path),
        "partner_packaging": str(packaging_path),
        "ecosystem_reliability": str(reliability_path),
        "ecosystem_drift_alerts": str(drift_path),
    }

    emitted_ecosystem = _read_json(ecosystem_path)
    emitted_packaging = _read_json(packaging_path)
    emitted_reliability = _read_json(reliability_path)
    emitted_drift = _read_json(drift_path)
    failures = _sorted_unique(
        failures
        + _validate_output_contracts(
            emitted_ecosystem,
            emitted_packaging,
            emitted_reliability,
            emitted_drift,
        )
    )

    result = _build_result_payload(
        failures=failures,
        ecosystem_payload=ecosystem_payload,
        out_dir=out_dir,
        artifacts=artifacts,
    )

    if ns.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "phase5-ecosystem-contract: OK" if result["ok"] else "phase5-ecosystem-contract: FAIL"
        )
        for row in result["checks"]:
            print(f"[{'OK' if row.get('ok') else 'FAIL'}] {row.get('id')}")
        for failure in failures:
            print(f"- {failure}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
