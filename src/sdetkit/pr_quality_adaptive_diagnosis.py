from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

JsonObject = dict[str, Any]
ADAPTIVE_DIAGNOSIS_SCHEMA_VERSION = "sdetkit.adaptive_diagnosis_card.v1"
ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION = "sdetkit.adaptive_diagnosis_export.v1"
ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION = (
    "sdetkit.adaptive_diagnosis_bundle_manifest.v1"
)
AUTHORITY_FIELDS = (
    "reporting_only",
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)
AUTHORITY_EXPECTATIONS = {
    "reporting_only": True,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

_FAILURE_CLASS_BY_CODE = {
    "PYTEST_ASSERTION_FAILURE": "test",
    "PRE_COMMIT_FORMAT_DRIFT": "formatter_only",
    "RUFF_LINT_FAILURE": "lint",
    "MYPY_TYPE_FAILURE": "type",
    "DEPENDENCY_RESOLUTION_FAILURE": "dependency",
    "RELEASE_ARTIFACT_INVALID": "release",
    "SECURITY_REVIEW_REQUIRED": "security",
    "UNKNOWN_REVIEW_REQUIRED": "unknown",
}
_GENERIC_OBSERVED = {
    *(f"assert {suffix}" for suffix in ("false is true", "true is false", "none", "0")),
    "check reported failure without detailed output",
}


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def adaptive_diagnosis_card(model: Mapping[str, object]) -> JsonObject:
    card = _as_dict(model.get("adaptive_diagnosis"))
    if card:
        return card
    return _as_dict(_as_dict(model.get("primary_failure")).get("adaptive_diagnosis"))


def validate_authority(card: Mapping[str, object]) -> None:
    mismatches = [
        f"{field} expected {expected!r}, observed {card.get(field)!r}"
        for field, expected in AUTHORITY_EXPECTATIONS.items()
        if card.get(field) is not expected
    ]
    if mismatches:
        raise ValueError(
            "unsafe adaptive diagnosis authority: " + "; ".join(mismatches)
        )


def build_export(card: Mapping[str, object]) -> JsonObject:
    checks = {
        _text(name): bool(value)
        for name, value in _as_dict(card.get("checks")).items()
        if _text(name)
    }
    return {
        "schema_version": ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION,
        "diagnosis": {
            "status": _text(card.get("status"), "review_first"),
            "failure_class": _text(card.get("failure_class"), "unknown"),
            "diagnostic_completeness": _text(
                card.get("diagnostic_completeness"), "insufficient"
            ),
            "confidence": _text(card.get("confidence"), "low"),
            "review_first": bool(card.get("review_first", True)),
        },
        "evidence": {
            "checks": checks,
            "owner_files": [
                _text(item) for item in _as_list(card.get("owner_files")) if _text(item)
            ],
            "proof_commands": [
                _text(item)
                for item in _as_list(card.get("proof_commands"))
                if _text(item)
            ],
            "evidence_gaps": [
                _text(item)
                for item in _as_list(card.get("evidence_gaps"))
                if _text(item)
            ],
            "next_human_action": _text(
                card.get("next_human_action"),
                "Collect exact failure evidence before changing code.",
            ),
        },
        "authority": {
            field: bool(card.get(field, False)) for field in AUTHORITY_FIELDS
        },
    }


def export_from_model(model: Mapping[str, object]) -> JsonObject:
    card = adaptive_diagnosis_card(model)
    if not card:
        raise ValueError("review model has no adaptive diagnosis card")
    return build_export(card)


def serialize_export(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _family_score(value: object) -> tuple[int, int, int]:
    family = _as_dict(value)
    code = _text(family.get("failure_code"))
    return (
        1 if _text(family.get("test_node")) else 0,
        1 if _text(family.get("message")) else 0,
        1
        if code and code not in {"UNKNOWN_REVIEW_REQUIRED", "RELEASE_ARTIFACT_INVALID"}
        else 0,
    )


def _richest_family(
    primary_failure: JsonObject, review_model: JsonObject
) -> JsonObject:
    families = [
        _as_dict(item)
        for item in _as_list(
            primary_failure.get("families") or review_model.get("failure_families")
        )
        if _as_dict(item)
    ]
    return max(families, key=_family_score) if families else {}


def _test_source_path(test_node: str) -> str:
    path = test_node.split("::", 1)[0].strip()
    return path if path.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".go")) else ""


def _generic_observation(value: str) -> bool:
    normalized = " ".join(value.lower().split())
    return normalized in _GENERIC_OBSERVED or normalized.startswith(
        "assert false is true"
    )


def _failure_class(primary_failure: JsonObject, detail: JsonObject) -> str:
    code = _text(
        primary_failure.get("diagnostic_failure_code")
        or detail.get("failure_code")
        or primary_failure.get("failure_code")
    )
    if code in _FAILURE_CLASS_BY_CODE:
        return _FAILURE_CLASS_BY_CODE[code]
    tool = _text(primary_failure.get("tool")).lower()
    return {"pytest": "test", "ruff": "lint", "mypy": "type"}.get(tool, "unknown")


def _owner_files(primary_failure: JsonObject) -> list[str]:
    candidates = [
        _text(primary_failure.get("source_path")),
        _test_source_path(_text(primary_failure.get("test_node"))),
    ]
    owners: list[str] = []
    for candidate in candidates:
        normalized = candidate.replace("\\", "/").removeprefix("./")
        if normalized and normalized not in owners:
            owners.append(normalized)
    return owners


def _proof_commands(primary_failure: JsonObject) -> list[str]:
    command = _text(primary_failure.get("reproduction_command"))
    if command:
        return [command]
    test_node = _text(primary_failure.get("test_node"))
    if test_node:
        return [f"python -m pytest -q {test_node} -o addopts="]
    return []


def _authority_boundary_preserved(primary_failure: JsonObject) -> bool:
    return bool(primary_failure.get("reporting_only", True)) and not any(
        bool(primary_failure.get(field, False))
        for field in AUTHORITY_FIELDS
        if field != "reporting_only"
    )


def attach_adaptive_diagnosis(review_model: JsonObject) -> None:
    primary_failure = _as_dict(review_model.get("primary_failure"))
    if not primary_failure or not bool(primary_failure.get("available", False)):
        return

    detail = _richest_family(primary_failure, review_model)
    observed = _text(primary_failure.get("observed"))
    expected = _text(primary_failure.get("expected"))
    message = _text(primary_failure.get("message"))
    owners = _owner_files(primary_failure)
    proof_commands = _proof_commands(primary_failure)

    checks = {
        "exact_failure_detail_present": bool(message)
        and not _generic_observation(observed),
        "expected_observed_specific": bool(expected)
        and expected != "check completes successfully"
        and bool(observed)
        and not _generic_observation(observed),
        "owner_file_resolved": bool(owners),
        "reproduction_command_resolved": bool(proof_commands),
        "step_provenance_confirmed": (
            _text(primary_failure.get("provenance_status")) == "confirmed"
            and _text(primary_failure.get("step_evidence_status")) == "confirmed"
            and bool(primary_failure.get("workflow_exact_head_verified", False))
        ),
        "authority_boundary_preserved": _authority_boundary_preserved(primary_failure),
    }
    existing_gaps = [
        _text(item)
        for item in _as_list(primary_failure.get("evidence_gaps"))
        if _text(item)
    ]
    evidence_gaps = list(existing_gaps)
    for check, passed in checks.items():
        if not passed and check not in evidence_gaps:
            evidence_gaps.append(check)

    diagnostic_checks = [
        name for name in checks if name != "authority_boundary_preserved"
    ]
    passed_count = sum(1 for name in diagnostic_checks if checks[name])
    if passed_count == len(diagnostic_checks):
        completeness = "complete"
    elif passed_count >= 3:
        completeness = "partial"
    else:
        completeness = "insufficient"

    mapping_confidence = _text(primary_failure.get("mapping_confidence"), "unknown")
    if completeness == "complete" and mapping_confidence == "high":
        confidence = "high"
    elif completeness == "insufficient" or mapping_confidence == "low":
        confidence = "low"
    else:
        confidence = "medium"

    failure_class = _failure_class(primary_failure, detail)
    review_first = (
        failure_class in {"test", "dependency", "release", "security", "unknown"}
        or completeness != "complete"
    )
    if proof_commands:
        next_human_action = (
            f"Run `{proof_commands[0]}`, inspect {', '.join(owners) or 'the failing surface'}, "
            "and review the first violated contract before changing code."
        )
    else:
        next_human_action = (
            "Collect the first specific assertion and an exact local reproduction command "
            "before changing code."
        )

    card = {
        "schema_version": ADAPTIVE_DIAGNOSIS_SCHEMA_VERSION,
        "status": "review_first" if review_first else "actionable",
        "failure_class": failure_class,
        "diagnostic_completeness": completeness,
        "diagnostic_check_count": len(checks),
        "diagnostic_checks_passed": sum(1 for passed in checks.values() if passed),
        "confidence": confidence,
        "checks": checks,
        "evidence_gaps": evidence_gaps,
        "owner_files": owners,
        "proof_commands": proof_commands,
        "next_human_action": next_human_action,
        "review_first": review_first,
        **AUTHORITY_EXPECTATIONS,
    }
    primary_failure["adaptive_diagnosis"] = card
    primary_failure["diagnostic_completeness"] = completeness
    primary_failure["diagnostic_confidence"] = confidence
    primary_failure["failure_class"] = failure_class
    primary_failure["owner_files"] = owners
    primary_failure["proof_commands"] = proof_commands
    primary_failure["next_human_action"] = next_human_action
    primary_failure["evidence_gaps"] = evidence_gaps
    if proof_commands and not _text(primary_failure.get("reproduction_command")):
        primary_failure["reproduction_command"] = proof_commands[0]
    review_model["adaptive_diagnosis"] = card
