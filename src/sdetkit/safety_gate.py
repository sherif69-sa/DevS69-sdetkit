from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sdetkit.failure_vector import FailureVector

SCHEMA_VERSION = "sdetkit.safety_gate.v1"

SAFE_FIX_CLASSES = frozenset({"formatter_only", "lint"})

GENERAL_BLOCKED_ACTIONS = (
    "delete or weaken tests",
    "skip CI or verifier checks",
    "edit workflow gates to hide the failure",
    "modify files outside allowed_files",
)


@dataclass(frozen=True)
class SafetyGateDecision:
    failure_class: str
    risk: str
    scope: str
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


def evaluate_failure_vector(vector: FailureVector) -> SafetyGateDecision:
    safe_fix_allowed = _safe_fix_allowed(vector)

    return SafetyGateDecision(
        failure_class=vector.failure_class,
        risk=vector.risk,
        scope=vector.scope,
        safe_fix_allowed=safe_fix_allowed,
        review_first=not safe_fix_allowed,
        reason=_decision_reason(vector, safe_fix_allowed),
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
            f"- safe_fix_allowed: `{allowed}`",
            f"- review_first: `{review_first}`",
            f"- reason: `{decision.reason}`",
            f"- allowed_files: `{allowed_files}`",
            f"- proof_commands: `{proof_commands}`",
            "",
        ]
    )


def _safe_fix_allowed(vector: FailureVector) -> bool:
    return (
        vector.safe_fix_candidate
        and vector.failure_class in SAFE_FIX_CLASSES
        and vector.risk == "low"
        and vector.scope == "pr_owned_only"
        and bool(vector.affected_files)
    )


def _decision_reason(vector: FailureVector, safe_fix_allowed: bool) -> str:
    if safe_fix_allowed:
        return "failure vector is low-risk, PR-owned, and mechanically eligible"
    if not vector.safe_fix_candidate:
        return (
            f"failure_class {vector.failure_class!r} is review-first or not mechanically eligible"
        )
    if not vector.affected_files:
        return "safe candidate lacks affected files, so patch scope cannot be verified"
    if vector.scope != "pr_owned_only":
        return f"scope {vector.scope!r} is not eligible for mechanical remediation"
    if vector.risk != "low":
        return f"risk {vector.risk!r} requires human review"
    return "failure vector does not satisfy SafetyGate eligibility"


def _proof_commands(vector: FailureVector) -> tuple[str, ...]:
    commands: list[str] = []
    if vector.local_repro_command:
        commands.append(vector.local_repro_command)
    commands.append("make proof-after-format")
    return tuple(commands)
