#!/usr/bin/env python3
"""Validate and emit Phase 4 governance payload contracts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.phase4_governance_contract.v2"
LEGACY_SCHEMA_VERSION = "sdetkit.phase4_governance_contract.v1"
RELEASE_EVIDENCE_SCHEMA_VERSION = "sdetkit.phase4_release_evidence.v1"
ADHERENCE_SCHEMA_VERSION = "sdetkit.phase4_governance_adherence.v1"

ALLOWED_CHECK_STATUSES = ("pass", "warn", "fail")
ALLOWED_POLICY_DOMAINS = (
    "contract",
    "compatibility",
    "release_evidence",
    "retention",
    "review_cadence",
)
ALLOWED_DECISION_DISPOSITIONS = ("accepted", "rejected", "deferred")
ALLOWED_IMPACT_TIERS = ("now", "next", "monitor")
ALLOWED_EVIDENCE_STATUSES = ("complete", "incomplete")
ALLOWED_ADHERENCE_STATUSES = ("on_track", "due", "overdue", "unknown")
ALLOWED_DRIFT_STATUSES = ("healthy", "drift")
DRIFT_THRESHOLD = 2
DEFAULT_DRIFT_SCORE_BY_SIGNAL = {
    "governance_check_failures": 2,
    "release_missing_artifacts": 2,
    "adherence_status": 1,
}
COMPLIANCE_OVERLAY_DOMAINS = ("security", "privacy", "regulated")

REASON_CODES = (
    "contract_satisfied",
    "missing_required_reference",
    "retention_policy_missing",
    "compatibility_boundary_missing",
    "review_signal_missing",
)
RATIONALE_CODES = (
    "risk_mitigation",
    "compatibility_commitment",
    "audit_readiness",
    "operational_focus",
)

REQUIRED_INDEX_LINKS = [
    "- [Versioning and support posture](versioning-and-support.md)",
    "- [Stability levels](stability-levels.md)",
]
REQUIRED_GOV_DOCS = [
    "docs/versioning-and-support.md",
    "docs/stability-levels.md",
    "docs/integrations-and-extension-boundary.md",
]
REQUIRED_OPERATOR_LINES = [
    "make phase4-governance-contract",
    "python scripts/validate_enterprise_contracts.py",
]


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sorted_unique(rows: list[str]) -> list[str]:
    return sorted({row for row in rows if row})


def _load_drift_scoring_config(path: Path) -> dict[str, int]:
    if not path.is_file():
        return dict(DEFAULT_DRIFT_SCORE_BY_SIGNAL)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_DRIFT_SCORE_BY_SIGNAL)
    if not isinstance(payload, dict):
        return dict(DEFAULT_DRIFT_SCORE_BY_SIGNAL)

    scores = dict(DEFAULT_DRIFT_SCORE_BY_SIGNAL)
    for key in list(scores):
        value = payload.get(key)
        if isinstance(value, int) and value >= 0:
            scores[key] = value
    return scores


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_row(
    *, check_id: str, ok: bool, evidence_refs: list[str], policy_domain: str
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if ok else "fail",
        "reason_code": "contract_satisfied" if ok else "missing_required_reference",
        "evidence_refs": _sorted_unique(evidence_refs) or ["missing:evidence"],
        "owner_hint": "governance-ops",
        "policy_domain": policy_domain,
    }


def _build_governance_payload(ns: argparse.Namespace) -> dict[str, Any]:
    docs_index = Path(ns.docs_index)
    operator = Path(ns.operator_essentials)

    docs_index_text = docs_index.read_text(encoding="utf-8") if docs_index.is_file() else ""
    operator_text = operator.read_text(encoding="utf-8") if operator.is_file() else ""

    checks: list[dict[str, Any]] = []
    checks.append(
        _check_row(
            check_id="docs_index_exists",
            ok=docs_index.is_file(),
            evidence_refs=[str(docs_index)],
            policy_domain="contract",
        )
    )
    for link in REQUIRED_INDEX_LINKS:
        checks.append(
            _check_row(
                check_id=f"docs_index_link::{link}",
                ok=link in docs_index_text,
                evidence_refs=[str(docs_index), link],
                policy_domain="contract",
            )
        )

    for path_text in REQUIRED_GOV_DOCS:
        p = Path(path_text)
        checks.append(
            _check_row(
                check_id=f"gov_doc_exists::{path_text}",
                ok=p.is_file(),
                evidence_refs=[path_text],
                policy_domain="compatibility",
            )
        )

    checks.append(
        _check_row(
            check_id="operator_essentials_exists",
            ok=operator.is_file(),
            evidence_refs=[str(operator)],
            policy_domain="review_cadence",
        )
    )
    for line in REQUIRED_OPERATOR_LINES:
        checks.append(
            _check_row(
                check_id=f"operator_line::{line}",
                ok=line in operator_text,
                evidence_refs=[str(operator), line],
                policy_domain="review_cadence",
            )
        )

    checks.sort(key=lambda row: str(row["check_id"]))

    policy_decisions = [
        {
            "decision_id": "phase4.compatibility.boundary.v1",
            "policy_id": "compatibility-boundary",
            "disposition": "accepted",
            "rationale_code": "compatibility_commitment",
            "impact_tier": "now",
        },
        {
            "decision_id": "phase4.release.evidence.retention.v1",
            "policy_id": "release-evidence-retention",
            "disposition": "accepted",
            "rationale_code": "audit_readiness",
            "impact_tier": "next",
        },
    ]
    policy_decisions.sort(key=lambda row: str(row["decision_id"]))

    compatibility_contract = {
        "supported_tiers": ["tier0", "tier1", "tier2"],
        "deprecation_boundaries": [
            "No tier removal without one release-cycle notice.",
            "Public CLI aliases remain available for one major cycle.",
        ],
        "compatibility_guards": [
            "make phase3-quality-contract",
            "make phase4-governance-contract",
        ],
    }
    compatibility_contract["supported_tiers"] = _sorted_unique(
        compatibility_contract["supported_tiers"]
    )
    compatibility_contract["deprecation_boundaries"] = _sorted_unique(
        compatibility_contract["deprecation_boundaries"]
    )
    compatibility_contract["compatibility_guards"] = _sorted_unique(
        compatibility_contract["compatibility_guards"]
    )

    release_evidence_contract = {
        "required_artifacts": _sorted_unique(
            [
                *REQUIRED_GOV_DOCS,
                str(operator),
                str(docs_index),
            ]
        ),
        "retention_window_days": 90,
        "auditability_status": "pass",
    }

    failures = _validate_policy_and_compatibility(
        governance_checks=checks,
        policy_decisions=policy_decisions,
        compatibility_contract=compatibility_contract,
        release_evidence_contract=release_evidence_contract,
    )

    legacy_checks = [
        {
            "id": row["check_id"],
            "ok": row["status"] == "pass",
            "reason_code": row["reason_code"],
        }
        for row in checks
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "legacy_schema_version": LEGACY_SCHEMA_VERSION,
        "migration_note": "v2 adds governance_checks/policy_decisions and dual-writes legacy checks.",
        "governance_checks": checks,
        "policy_decisions": policy_decisions,
        "compatibility_contract": compatibility_contract,
        "release_evidence_contract": release_evidence_contract,
        "generated_at": _now_utc(),
        # one-cycle legacy bridge
        "ok": not failures,
        "checks": legacy_checks,
        "failures": failures,
    }


def _render_release_evidence_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 4 release evidence",
        "",
        f"- schema_version: `{payload.get('schema_version', '')}`",
        f"- evidence_status: `{payload.get('evidence_status', '')}`",
        f"- retention_window_days: `{payload.get('retention_window_days', '')}`",
        "",
        "## Required artifacts",
    ]
    for item in payload.get("required_artifacts", []):
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("## Missing artifacts")
    missing = payload.get("missing_artifacts", [])
    if missing:
        for item in missing:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append(f"- generated_at: `{payload.get('generated_at', '')}`")
    return "\n".join(lines) + "\n"


def _build_release_evidence(governance_payload: dict[str, Any]) -> dict[str, Any]:
    contract = governance_payload.get("release_evidence_contract", {})
    required = _sorted_unique(list(contract.get("required_artifacts", [])))
    discovered = _sorted_unique([path for path in required if Path(path).is_file()])
    missing = _sorted_unique(sorted(set(required) - set(discovered)))
    evidence_status = "complete" if not missing else "incomplete"
    return {
        "schema_version": RELEASE_EVIDENCE_SCHEMA_VERSION,
        "required_artifacts": required,
        "discovered_artifacts": discovered,
        "missing_artifacts": missing,
        "retention_window_days": int(contract.get("retention_window_days", 0) or 0),
        "evidence_status": evidence_status,
        "generated_at": _now_utc(),
    }


def _build_adherence_payload(ns: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    recommendations: list[str] = []
    adherence_failures: list[str] = []
    review_cadence_days = int(ns.review_cadence_days)
    last_review_at = str(ns.last_review_at or "").strip()
    next_due = ""
    adherence_status = "unknown"

    if not last_review_at:
        blockers.append("last_review_at_missing")
        recommendations.append("Set --last-review-at (YYYY-MM-DD) to enable schedule tracking.")
        recommendations.append("Run governance review and update adherence artifact in CI.")
    else:
        try:
            review_date = date.fromisoformat(last_review_at)
        except ValueError:
            blockers.append("last_review_at_invalid")
            adherence_failures.append("last_review_at must use YYYY-MM-DD")
            recommendations.append("Fix --last-review-at format to YYYY-MM-DD.")
        else:
            next_due_date = review_date + timedelta(days=review_cadence_days)
            next_due = next_due_date.isoformat()
            today = datetime.now(UTC).date()
            delta = (next_due_date - today).days
            if delta > 0:
                adherence_status = "on_track"
            elif delta == 0:
                adherence_status = "due"
                recommendations.append("Complete governance review today.")
            else:
                adherence_status = "overdue"
                blockers.append("review_cadence_breached")
                recommendations.append("Run governance review immediately and record signoff.")

    return {
        "schema_version": ADHERENCE_SCHEMA_VERSION,
        "review_cadence_days": review_cadence_days,
        "last_review_at": last_review_at,
        "next_review_due_at": next_due,
        "adherence_status": adherence_status,
        "blockers": _sorted_unique(blockers),
        "recommended_actions": _sorted_unique(recommendations),
    }, _sorted_unique(adherence_failures)


def _validate_policy_and_compatibility(
    *,
    governance_checks: list[dict[str, Any]],
    policy_decisions: list[dict[str, Any]],
    compatibility_contract: dict[str, Any],
    release_evidence_contract: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    for row in governance_checks:
        if str(row.get("status", "")) not in ALLOWED_CHECK_STATUSES:
            failures.append(f"invalid governance_checks.status: {row.get('status')}")
        if str(row.get("reason_code", "")) not in REASON_CODES:
            failures.append(f"invalid governance_checks.reason_code: {row.get('reason_code')}")
        evidence = row.get("evidence_refs", [])
        if not isinstance(evidence, list) or not evidence:
            failures.append(f"missing governance_checks.evidence_refs for {row.get('check_id')}")
        if str(row.get("policy_domain", "")) not in ALLOWED_POLICY_DOMAINS:
            failures.append(f"invalid governance_checks.policy_domain: {row.get('policy_domain')}")

    for row in policy_decisions:
        if str(row.get("disposition", "")) not in ALLOWED_DECISION_DISPOSITIONS:
            failures.append(f"invalid policy_decisions.disposition: {row.get('decision_id')}")
        if str(row.get("rationale_code", "")) not in RATIONALE_CODES:
            failures.append(
                f"missing/invalid policy_decisions.rationale_code: {row.get('decision_id')}"
            )
        if str(row.get("impact_tier", "")) not in ALLOWED_IMPACT_TIERS:
            failures.append(
                f"missing/invalid policy_decisions.impact_tier: {row.get('decision_id')}"
            )

    if not compatibility_contract.get("deprecation_boundaries"):
        failures.append("compatibility_contract.deprecation_boundaries missing/empty")
    if not compatibility_contract.get("compatibility_guards"):
        failures.append("compatibility_contract.compatibility_guards missing/empty")

    artifacts = release_evidence_contract.get("required_artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        failures.append("release_evidence_contract.required_artifacts missing/empty")
    if int(release_evidence_contract.get("retention_window_days", 0) or 0) <= 0:
        failures.append("release_evidence_contract.retention_window_days missing/invalid")

    return _sorted_unique(failures)


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


def _validate_output_contracts(
    governance_payload: dict[str, Any],
    release_payload: dict[str, Any],
    adherence_payload: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    for key in (
        "schema_version",
        "governance_checks",
        "policy_decisions",
        "compatibility_contract",
        "release_evidence_contract",
        "generated_at",
    ):
        if key not in governance_payload:
            failures.append(f"governance payload missing key: {key}")

    governance_checks = governance_payload.get("governance_checks", [])
    policy_decisions = governance_payload.get("policy_decisions", [])
    compatibility_contract = governance_payload.get("compatibility_contract", {})
    release_evidence_contract = governance_payload.get("release_evidence_contract", {})

    if not isinstance(compatibility_contract, dict):
        failures.append("compatibility_contract must be an object")
    if not isinstance(release_evidence_contract, dict):
        failures.append("release_evidence_contract must be an object")

    if isinstance(governance_checks, list) and isinstance(policy_decisions, list):
        failures.extend(
            _validate_policy_and_compatibility(
                governance_checks=list(governance_checks),
                policy_decisions=list(policy_decisions),
                compatibility_contract=(
                    dict(compatibility_contract) if isinstance(compatibility_contract, dict) else {}
                ),
                release_evidence_contract=(
                    dict(release_evidence_contract)
                    if isinstance(release_evidence_contract, dict)
                    else {}
                ),
            )
        )

    failures.extend(
        _validate_deterministic_dict_list(governance_payload, "governance_checks", "check_id")
    )
    failures.extend(
        _validate_deterministic_dict_list(governance_payload, "policy_decisions", "decision_id")
    )

    for key in (
        "schema_version",
        "required_artifacts",
        "discovered_artifacts",
        "missing_artifacts",
        "retention_window_days",
        "evidence_status",
        "generated_at",
    ):
        if key not in release_payload:
            failures.append(f"release evidence missing key: {key}")
    for list_key in ("required_artifacts", "discovered_artifacts", "missing_artifacts"):
        rows = release_payload.get(list_key, [])
        if not isinstance(rows, list) or rows != sorted(rows):
            failures.append(f"release evidence {list_key} must be sorted list")
    if str(release_payload.get("evidence_status", "")) not in ALLOWED_EVIDENCE_STATUSES:
        failures.append(
            f"invalid release evidence status: {release_payload.get('evidence_status')}"
        )

    for key in (
        "schema_version",
        "review_cadence_days",
        "last_review_at",
        "next_review_due_at",
        "adherence_status",
        "blockers",
        "recommended_actions",
    ):
        if key not in adherence_payload:
            failures.append(f"adherence payload missing key: {key}")
    for list_key in ("blockers", "recommended_actions"):
        rows = adherence_payload.get(list_key, [])
        if not isinstance(rows, list) or rows != sorted(rows):
            failures.append(f"adherence {list_key} must be sorted list")
    if str(adherence_payload.get("adherence_status", "")) not in ALLOWED_ADHERENCE_STATUSES:
        failures.append(f"invalid adherence status: {adherence_payload.get('adherence_status')}")
    if (
        not adherence_payload.get("last_review_at")
        and adherence_payload.get("adherence_status") != "unknown"
    ):
        failures.append("missing last_review_at must produce unknown adherence_status")
    if not adherence_payload.get("last_review_at") and not adherence_payload.get(
        "recommended_actions"
    ):
        failures.append("missing last_review_at must provide actionable recommendations")

    return _sorted_unique(failures)


def _build_compliance_overlay_pack() -> dict[str, Any]:
    overlays = [
        {
            "domain": domain,
            "controls": [
                f"{domain}.evidence_retention",
                f"{domain}.compatibility_boundary",
                f"{domain}.review_cadence",
            ],
            "owner_hint": "governance-ops",
        }
        for domain in COMPLIANCE_OVERLAY_DOMAINS
    ]
    overlays.sort(key=lambda row: str(row["domain"]))
    return {
        "schema_version": "sdetkit.phase4_compliance_overlay_pack.v1",
        "overlays": overlays,
        "generated_at": _now_utc(),
    }


def _emit_domain_overlay_files(out_dir: Path, compliance_overlay: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for row in compliance_overlay.get("overlays", []):
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain", "")).strip()
        if not domain:
            continue
        path = out_dir / f"phase4-compliance-overlay-{domain}.json"
        _write_json(
            path,
            {
                "schema_version": "sdetkit.phase4_compliance_overlay.v1",
                "domain": domain,
                "controls": sorted(str(item) for item in row.get("controls", [])),
                "owner_hint": str(row.get("owner_hint", "governance-ops")),
                "generated_at": _now_utc(),
            },
        )
        paths.append(str(path))
    return sorted(paths)


def _build_policy_as_code_template() -> dict[str, Any]:
    rules = [
        {"rule_id": "compatibility.boundary", "enforcement": "required", "severity": "high"},
        {"rule_id": "release.evidence.retention", "enforcement": "required", "severity": "high"},
        {"rule_id": "review.cadence", "enforcement": "warn", "severity": "medium"},
    ]
    rules.sort(key=lambda row: str(row["rule_id"]))
    return {
        "schema_version": "sdetkit.phase4_policy_as_code_template.v1",
        "target": "partner-repo",
        "rules": rules,
        "generated_at": _now_utc(),
    }


def _build_governance_drift_alerts(
    governance_payload: dict[str, Any],
    release_payload: dict[str, Any],
    adherence_payload: dict[str, Any],
    *,
    score_by_signal: dict[str, int] | None = None,
    drift_threshold: int = DRIFT_THRESHOLD,
) -> dict[str, Any]:
    alerts: list[str] = []
    drift_score = 0
    scores = score_by_signal or DEFAULT_DRIFT_SCORE_BY_SIGNAL

    failed_checks = [
        str(row.get("check_id", ""))
        for row in governance_payload.get("governance_checks", [])
        if isinstance(row, dict) and str(row.get("status", "")) != "pass"
    ]
    if failed_checks:
        alerts.append(f"governance_check_failures:{','.join(sorted(failed_checks))}")
        drift_score += int(scores.get("governance_check_failures", 0))

    missing_artifacts = release_payload.get("missing_artifacts", [])
    if isinstance(missing_artifacts, list) and missing_artifacts:
        alerts.append(
            f"release_missing_artifacts:{','.join(sorted(str(x) for x in missing_artifacts))}"
        )
        drift_score += int(scores.get("release_missing_artifacts", 0))

    adherence_status = str(adherence_payload.get("adherence_status", ""))
    if adherence_status in {"due", "overdue", "unknown"}:
        alerts.append(f"adherence_status:{adherence_status}")
        drift_score += int(scores.get("adherence_status", 0))

    drift_status = "drift" if drift_score >= int(drift_threshold) else "healthy"
    return {
        "schema_version": "sdetkit.phase4_governance_drift_alerts.v1",
        "drift_status": drift_status,
        "alerts": sorted(alerts),
        "drift_score": drift_score,
        "drift_threshold": int(drift_threshold),
        "generated_at": _now_utc(),
    }


def _render_drift_alerts_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 4 governance drift alerts",
        "",
        f"- drift_status: `{payload.get('drift_status', '')}`",
        f"- drift_score: `{payload.get('drift_score', '')}`",
        f"- drift_threshold: `{payload.get('drift_threshold', '')}`",
        "",
        "## Alerts",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append(f"- generated_at: `{payload.get('generated_at', '')}`")
    return "\n".join(lines) + "\n"


def _validate_drift_alerts(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key in (
        "schema_version",
        "drift_status",
        "alerts",
        "drift_score",
        "drift_threshold",
        "generated_at",
    ):
        if key not in payload:
            failures.append(f"drift alerts missing key: {key}")
    alerts = payload.get("alerts", [])
    if not isinstance(alerts, list) or alerts != sorted(alerts):
        failures.append("drift alerts list must be sorted")
    if str(payload.get("drift_status", "")) not in ALLOWED_DRIFT_STATUSES:
        failures.append(f"invalid drift_status: {payload.get('drift_status')}")
    if not isinstance(payload.get("drift_score"), int):
        failures.append("drift_score must be int")
    threshold_value = payload.get("drift_threshold", -1)
    if not isinstance(threshold_value, int) or threshold_value < 0:
        failures.append("drift_threshold must be non-negative int")
    return _sorted_unique(failures)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-index", default="docs/index.md")
    ap.add_argument("--operator-essentials", default="docs/operator-essentials.md")
    ap.add_argument("--out-dir", default="build/phase4-governance")
    ap.add_argument("--review-cadence-days", type=int, default=30)
    ap.add_argument("--last-review-at", default="")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--no-md", action="store_true", help="Skip phase4-release-evidence.md emission")
    ap.add_argument("--drift-scoring-config", default="config/phase4_drift_scoring.json")
    ap.add_argument("--drift-threshold", type=int, default=DRIFT_THRESHOLD)
    ns = ap.parse_args(argv)

    out_dir = Path(ns.out_dir)
    governance_payload = _build_governance_payload(ns)
    release_payload = _build_release_evidence(governance_payload)
    adherence_payload, adherence_failures = _build_adherence_payload(ns)
    compliance_overlay = _build_compliance_overlay_pack()
    policy_template = _build_policy_as_code_template()
    drift_scores = _load_drift_scoring_config(Path(ns.drift_scoring_config))
    drift_alerts = _build_governance_drift_alerts(
        governance_payload,
        release_payload,
        adherence_payload,
        score_by_signal=drift_scores,
        drift_threshold=max(0, int(ns.drift_threshold)),
    )

    _write_json(out_dir / "phase4-governance-contract.json", governance_payload)
    _write_json(out_dir / "phase4-release-evidence.json", release_payload)
    release_md_path = out_dir / "phase4-release-evidence.md"
    if not ns.no_md:
        release_md_path.write_text(
            _render_release_evidence_markdown(release_payload), encoding="utf-8"
        )
    _write_json(out_dir / "phase4-governance-adherence.json", adherence_payload)
    _write_json(out_dir / "phase4-compliance-overlay-pack.json", compliance_overlay)
    domain_overlay_paths = _emit_domain_overlay_files(out_dir, compliance_overlay)
    _write_json(out_dir / "phase4-policy-as-code-template.json", policy_template)
    _write_json(out_dir / "phase4-governance-drift-alerts.json", drift_alerts)
    (out_dir / "phase4-governance-drift-alerts.md").write_text(
        _render_drift_alerts_markdown(drift_alerts), encoding="utf-8"
    )

    failures = _validate_output_contracts(governance_payload, release_payload, adherence_payload)
    failures.extend(_validate_drift_alerts(drift_alerts))
    failures.extend(adherence_failures)
    failures.extend(_sorted_unique([str(item) for item in governance_payload.get("failures", [])]))
    check_failures = [
        f"governance check failed: {row.get('check_id', '')}"
        for row in governance_payload.get("governance_checks", [])
        if isinstance(row, dict) and row.get("status") != "pass"
    ]
    failures.extend(_sorted_unique(check_failures))
    failures = _sorted_unique(failures)

    checks = [
        {"id": "schema_completeness", "ok": not any("missing key" in msg for msg in failures)},
        {
            "id": "policy_compatibility_enforcement",
            "ok": not any(
                "compatibility_contract" in msg
                or "release_evidence_contract" in msg
                or "governance_checks" in msg
                or "policy_decisions" in msg
                for msg in failures
            ),
        },
        {
            "id": "release_evidence_presence_schema",
            "ok": not any(msg.startswith("release evidence") for msg in failures),
        },
        {
            "id": "adherence_presence_schema",
            "ok": not any(msg.startswith("adherence") for msg in failures),
        },
        {
            "id": "deterministic_ordering",
            "ok": not any("sorted" in msg for msg in failures),
        },
        {
            "id": "reason_rationale_vocabulary_enforced",
            "ok": not any("reason_code" in msg or "rationale_code" in msg for msg in failures),
        },
        {
            "id": "drift_alerts_schema",
            "ok": not any(
                msg.startswith("drift alerts") or "drift_status" in msg for msg in failures
            ),
        },
    ]

    payload = {
        "ok": not failures,
        "schema_version": SCHEMA_VERSION,
        "checks": checks,
        "failures": failures,
        "artifacts": {
            "governance_contract": str(out_dir / "phase4-governance-contract.json"),
            "release_evidence": str(out_dir / "phase4-release-evidence.json"),
            "release_evidence_markdown": str(release_md_path) if not ns.no_md else "",
            "governance_adherence": str(out_dir / "phase4-governance-adherence.json"),
            "compliance_overlay_pack": str(out_dir / "phase4-compliance-overlay-pack.json"),
            "policy_as_code_template": str(out_dir / "phase4-policy-as-code-template.json"),
            "governance_drift_alerts": str(out_dir / "phase4-governance-drift-alerts.json"),
            "governance_drift_alerts_markdown": str(out_dir / "phase4-governance-drift-alerts.md"),
            "compliance_overlay_domain_artifacts": domain_overlay_paths,
        },
    }

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "phase4-governance-contract: OK"
            if payload["ok"]
            else "phase4-governance-contract: FAIL"
        )
        for check in checks:
            print(f"[{'OK' if check['ok'] else 'FAIL'}] {check['id']}")
        for failure in failures:
            print(f"- {failure}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
