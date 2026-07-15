from __future__ import annotations

from typing import Any

DOCTOR_SCHEMA_VERSION = "sdetkit.doctor.v2"
LEGACY_DOCTOR_SCHEMA_VERSION = "sdetkit.doctor.v1"
MALFORMED_DOCTOR_REASON = "doctor evidence unavailable or malformed"


def _check_failed(item: dict[str, Any]) -> bool:
    ok = item.get("ok")
    if isinstance(ok, bool):
        return not ok
    passed = item.get("passed")
    if isinstance(passed, bool):
        return not passed
    return False


def _failing_check_ids(checks: object) -> list[str]:
    failing: list[str] = []
    if isinstance(checks, dict):
        for check_id, item in checks.items():
            if isinstance(item, dict) and _check_failed(item):
                normalized = str(check_id).strip()
                if normalized:
                    failing.append(normalized)
        return sorted(set(failing))

    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict) or not _check_failed(item):
                continue
            check_id = item.get("name") or item.get("id") or item.get("key")
            normalized = str(check_id).strip() if check_id is not None else ""
            if normalized:
                failing.append(normalized)
        return sorted(set(failing))

    return []


def _doctor_status(payload: dict[str, Any], failing_checks: list[str]) -> str:
    status = payload.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip()

    ok = payload.get("ok")
    if isinstance(ok, bool):
        return "green" if ok else "blocked"

    quality = payload.get("quality")
    if isinstance(quality, dict):
        failed = quality.get("failed_checks")
        if isinstance(failed, int):
            return "green" if failed == 0 else "review_required"

    return "review_required" if failing_checks else "unknown"


def evaluate_doctor_evidence(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or "raw" in payload:
        return {
            "status": "unknown",
            "evidence_available": False,
            "failing_checks": [],
            "actionable_reasons": [MALFORMED_DOCTOR_REASON],
        }

    schema_version = payload.get("schema_version")
    checks = payload.get("checks")
    current_shape = schema_version == DOCTOR_SCHEMA_VERSION and isinstance(checks, dict)
    legacy_shape = (
        schema_version in {None, "", LEGACY_DOCTOR_SCHEMA_VERSION, DOCTOR_SCHEMA_VERSION}
        and isinstance(checks, list)
    )
    evidence_available = current_shape or legacy_shape
    if not evidence_available:
        return {
            "status": "unknown",
            "evidence_available": False,
            "failing_checks": [],
            "actionable_reasons": [MALFORMED_DOCTOR_REASON],
        }

    failing_checks = _failing_check_ids(checks)
    actionable_reasons = (
        [f"failing doctor checks: {len(failing_checks)}"] if failing_checks else []
    )
    return {
        "status": _doctor_status(payload, failing_checks),
        "evidence_available": True,
        "failing_checks": failing_checks,
        "actionable_reasons": actionable_reasons,
    }
