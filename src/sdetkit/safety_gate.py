from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

SCHEMA_VERSION = "sdetkit.safety_gate.v1"

FALSE_AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_claim",
)


class FailureVectorLike(Protocol):
    @property
    def failure_class(self) -> str: ...

    @property
    def risk(self) -> str: ...

    @property
    def scope(self) -> str: ...

    @property
    def safe_fix_candidate(self) -> bool: ...

    @property
    def affected_files(self) -> tuple[str, ...]: ...

    @property
    def local_repro_command(self) -> str | None: ...


SAFE_FIX_CLASSES = frozenset({"formatter_only", "lint"})

GENERAL_BLOCKED_ACTIONS = (
    "delete or " "weaken tests",
    "skip CI or " "verifier checks",
    "edit workflow gates " "to hide the failure",
    "modify files outside allowed_files",
)


@dataclass(frozen=True)
class SafetyGateDecision:
    failure_class: str
    risk: str
    scope: str
    failure_kind: str
    affected_surface: str
    ownership_area: str
    retryability: str
    security_relevance: bool
    recommended_next_human_action: str
    reporting_only: bool
    automation_allowed: bool
    patch_application_allowed: bool
    security_dismissal_allowed: bool
    merge_authorized: bool
    semantic_equivalence_claim: bool
    safe_fix_allowed: bool
    review_first: bool
    reason: str
    allowed_files: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    proof_commands: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed_files"] = list(self.allowed_files)
        payload["blocked_actions"] = list(self.blocked_actions)
        payload["proof_commands"] = list(self.proof_commands)
        return payload


def evaluate_failure_vector(vector: FailureVectorLike) -> SafetyGateDecision:
    contract = _normalized_contract(vector)
    safe_fix_allowed = _safe_fix_allowed(vector, contract)

    return SafetyGateDecision(
        failure_class=vector.failure_class,
        risk=vector.risk,
        scope=vector.scope,
        failure_kind=str(contract["failure_kind"]),
        affected_surface=str(contract["affected_surface"]),
        ownership_area=str(contract["ownership_area"]),
        retryability=str(contract["retryability"]),
        security_relevance=bool(contract["security_relevance"]),
        recommended_next_human_action=str(contract["recommended_next_human_action"]),
        reporting_only=bool(contract["reporting_only"]),
        automation_allowed=bool(contract["automation_allowed"]),
        patch_application_allowed=bool(contract["patch_application_allowed"]),
        security_dismissal_allowed=bool(contract["security_dismissal_allowed"]),
        merge_authorized=bool(contract["merge_authorized"]),
        semantic_equivalence_claim=bool(contract["semantic_equivalence_claim"]),
        safe_fix_allowed=safe_fix_allowed,
        review_first=not safe_fix_allowed,
        reason=_decision_reason(vector, contract, safe_fix_allowed),
        allowed_files=vector.affected_files if safe_fix_allowed else (),
        blocked_actions=GENERAL_BLOCKED_ACTIONS,
        proof_commands=_proof_commands(vector),
    )


def write_safety_gate_decision(decision: SafetyGateDecision, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(decision.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_safety_gate_decision_report(decision: SafetyGateDecision) -> str:
    allowed = "yes" if decision.safe_fix_allowed else "no"
    review_first = "yes" if decision.review_first else "no"
    security_relevance = "yes" if decision.security_relevance else "no"
    reporting_only = "yes" if decision.reporting_only else "no"
    allowed_files = ", ".join(decision.allowed_files) if decision.allowed_files else "none"
    proof_commands = ", ".join(decision.proof_commands) if decision.proof_commands else "none"

    return "\n".join(
        [
            "# Safety Gate Decision",
            "",
            f"- schema_version: `{decision.schema_version}`",
            f"- failure_class: `{decision.failure_class}`",
            f"- risk: `{decision.risk}`",
            f"- scope: `{decision.scope}`",
            f"- failure_kind: `{decision.failure_kind}`",
            f"- affected_surface: `{decision.affected_surface}`",
            f"- ownership_area: `{decision.ownership_area}`",
            f"- retryability: `{decision.retryability}`",
            f"- security_relevance: `{security_relevance}`",
            (f"- recommended_next_human_action: `{decision.recommended_next_human_action}`"),
            f"- reporting_only: `{reporting_only}`",
            f"- safe_fix_allowed: `{allowed}`",
            f"- review_first: `{review_first}`",
            f"- reason: `{decision.reason}`",
            f"- allowed_files: `{allowed_files}`",
            f"- proof_commands: `{proof_commands}`",
            "- automation_allowed: `false`",
            "- patch_application_allowed: `false`",
            "- security_dismissal_allowed: `false`",
            "- merge_authorized: `false`",
            "- semantic_equivalence_claim: `false`",
            "",
        ]
    )


def _safe_fix_allowed(
    vector: FailureVectorLike,
    contract: Mapping[str, object],
) -> bool:
    return (
        _contract_preserves_authority_boundary(contract)
        and not bool(contract["security_relevance"])
        and str(contract["failure_kind"]) in SAFE_FIX_CLASSES
        and str(contract["retryability"]) != "human_review_required"
        and vector.safe_fix_candidate
        and vector.failure_class in SAFE_FIX_CLASSES
        and vector.risk == "low"
        and vector.scope == "pr_owned_only"
        and bool(vector.affected_files)
        and bool(vector.local_repro_command)
    )


def _decision_reason(
    vector: FailureVectorLike,
    contract: Mapping[str, object],
    safe_fix_allowed: bool,
) -> str:
    if safe_fix_allowed:
        return (
            "normalized failure-vector contract is low-risk, PR-owned, "
            "mechanically eligible, and has required proof"
        )
    if not _contract_preserves_authority_boundary(contract):
        return "normalized failure-vector contract does not preserve authority boundary"
    if bool(contract["security_relevance"]):
        return "normalized failure-vector contract marks this security-relevant"
    if str(contract["retryability"]) == "human_review_required":
        return (
            f"failure_class {vector.failure_class!r} requires human review "
            "by normalized failure-vector contract"
        )
    if not vector.safe_fix_candidate:
        return (
            f"failure_class {vector.failure_class!r} is review-first or not mechanically eligible"
        )
    if not vector.affected_files:
        return "safe candidate lacks affected files, so patch scope cannot be verified"
    if not vector.local_repro_command:
        return "safe candidate lacks local repro command, so required proof cannot be selected"
    if vector.scope != "pr_owned_only":
        return f"scope {vector.scope!r} is not eligible for mechanical remediation"
    if vector.risk != "low":
        return f"risk {vector.risk!r} requires human review"
    return "failure vector does not satisfy SafetyGate eligibility"


def _proof_commands(vector: FailureVectorLike) -> tuple[str, ...]:
    commands: list[str] = []
    if vector.local_repro_command:
        commands.append(vector.local_repro_command)
    commands.append("make proof-after-format")
    return tuple(commands)


def _normalized_contract(vector: FailureVectorLike) -> dict[str, object]:
    raw = _contract_from_vector(vector)
    return {
        "failure_kind": _contract_text(raw, "failure_kind", vector.failure_class),
        "affected_surface": _contract_text(
            raw,
            "affected_surface",
            _affected_surface(vector.affected_files),
        ),
        "ownership_area": _contract_text(
            raw,
            "ownership_area",
            _ownership_area(vector),
        ),
        "retryability": _contract_text(
            raw,
            "retryability",
            _retryability(vector.failure_class),
        ),
        "security_relevance": _contract_bool(
            raw,
            "security_relevance",
            vector.failure_class == "security",
        ),
        "recommended_next_human_action": _contract_text(
            raw,
            "recommended_next_human_action",
            "triage failure and rerun focused proof",
        ),
        "reporting_only": _contract_bool(raw, "reporting_only", True),
        "automation_allowed": _contract_bool(raw, "automation_allowed", False),
        "patch_application_allowed": _contract_bool(
            raw,
            "patch_application_allowed",
            False,
        ),
        "security_dismissal_allowed": _contract_bool(
            raw,
            "security_dismissal_allowed",
            False,
        ),
        "merge_authorized": _contract_bool(raw, "merge_authorized", False),
        "semantic_equivalence_claim": _contract_bool(
            raw,
            "semantic_equivalence_claim",
            False,
        ),
    }


def _contract_from_vector(vector: FailureVectorLike) -> Mapping[str, object]:
    to_dict = getattr(vector, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            contract = payload.get("contract")
            if isinstance(contract, Mapping):
                return contract

    contract = getattr(vector, "contract", None)
    if isinstance(contract, Mapping):
        return contract

    return {}


def _contract_text(
    contract: Mapping[str, object],
    key: str,
    default: str,
) -> str:
    value = contract.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _contract_bool(
    contract: Mapping[str, object],
    key: str,
    default: bool,
) -> bool:
    value = contract.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    if value is None:
        return default
    return bool(value)


def _contract_preserves_authority_boundary(contract: Mapping[str, object]) -> bool:
    return bool(contract["reporting_only"]) and all(
        not bool(contract[field]) for field in FALSE_AUTHORITY_FIELDS
    )


def _affected_surface(affected_files: tuple[str, ...]) -> str:
    if not affected_files:
        return "unknown"
    if all(path.startswith("tests/") for path in affected_files):
        return "tests"
    if all(path.startswith("src/") for path in affected_files):
        return "source"
    if all(path.startswith(("src/", "tests/")) for path in affected_files):
        return "code"
    return "repo_wide"


def _ownership_area(vector: FailureVectorLike) -> str:
    if vector.affected_files:
        return vector.affected_files[0]
    return "unknown"


def _retryability(failure_class: str) -> str:
    if failure_class in {"dependency", "merge_conflict", "release", "security", "unknown"}:
        return "human_review_required"
    return "not_retryable_without_change"
