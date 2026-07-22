from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = "sdetkit.decision_envelope.v2"
CONTRACT_SCHEMA_VERSION = "sdetkit.decision_envelope_contract.v2"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "branch_execution_allowed",
    "merge_authorized",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
)
AUTHORITY_ALIASES = {
    *AUTHORITY_FIELDS,
    "semantic_equivalence_claim",
}
BLOCKED_ACTIONS = (
    "apply_patch_without_authenticated_approval",
    "execute_on_branch_without_authenticated_approval",
    "mutate_default_branch",
    "merge_pull_request",
    "publish_release",
    "dismiss_security_findings",
    "claim_semantic_equivalence",
)
STATUSES = frozenset(
    {
        "blocked",
        "review_required",
        "eligible_for_proposal",
        "proposal_ready",
        "verified",
    }
)
PROPOSAL_READY_STATUSES = frozenset(
    {
        "eligible",
        "eligible_for_human_policy_proposal",
        "proposal_ready",
        "passed",
    }
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
JsonObject = dict[str, Any]


@dataclass(frozen=True)
class DecisionEnvelope:
    repository: str
    commit_sha: str
    status: str
    primary_blocker: str
    owner_surface: str
    confidence: str
    risk: str
    allowed_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    focused_proof: tuple[str, ...]
    quality_proof: tuple[str, ...]
    verifier_state: str
    next_human_action: str
    decision_id: str
    schema_version: str = SCHEMA_VERSION
    _failure_vector_json: str = field(repr=False, default="{}")
    _authority_json: str = field(repr=False, default="{}")
    _proposed_change_json: str | None = field(repr=False, default=None)
    _evidence_digests_json: str = field(repr=False, default="{}")

    @property
    def failure_vector(self) -> JsonObject:
        return _decode_object(self._failure_vector_json)

    @property
    def authority(self) -> dict[str, bool]:
        return cast(dict[str, bool], _decode_object(self._authority_json))

    @property
    def proposed_change(self) -> JsonObject | None:
        if self._proposed_change_json is None:
            return None
        return _decode_object(self._proposed_change_json)

    @property
    def evidence_digests(self) -> dict[str, str]:
        return cast(dict[str, str], _decode_object(self._evidence_digests_json))

    def to_dict(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "repository": self.repository,
            "commit_sha": self.commit_sha,
            "status": self.status,
            "primary_blocker": self.primary_blocker,
            "failure_vector": self.failure_vector,
            "owner_surface": self.owner_surface,
            "confidence": self.confidence,
            "risk": self.risk,
            "authority": self.authority,
            "allowed_actions": self.allowed_actions,
            "blocked_actions": self.blocked_actions,
            "proposed_change": self.proposed_change,
            "focused_proof": self.focused_proof,
            "quality_proof": self.quality_proof,
            "verifier_state": self.verifier_state,
            "next_human_action": self.next_human_action,
            "evidence_digests": dict(sorted(self.evidence_digests.items())),
        }


def build_decision_envelope(
    *,
    repository: str,
    commit_sha: str,
    failure_vector: Mapping[str, Any],
    safety_gate: Mapping[str, Any],
    proposal: Mapping[str, Any] | None = None,
    verifier: Mapping[str, Any] | None = None,
    quality_proof_commands: Sequence[str] = (),
    evidence_digests: Mapping[str, str] | None = None,
) -> DecisionEnvelope:
    _validate_identity(repository, commit_sha)
    failure = _json_object(failure_vector, "failure_vector")
    safety = _json_object(safety_gate, "safety_gate")
    proposal_payload = _optional_object(proposal, "proposal")
    verifier_payload = _optional_object(verifier, "verifier")

    for name, payload in (
        ("failure_vector", failure),
        ("safety_gate", safety),
        ("proposal", proposal_payload),
        ("verifier", verifier_payload),
    ):
        if payload is not None:
            _assert_authority_denied(payload, name)
    for name, payload in (
        ("proposal", proposal_payload),
        ("verifier", verifier_payload),
    ):
        if payload is not None:
            _assert_exact_head(payload, repository, commit_sha, name)

    contract = _mapping(failure.get("contract"))
    failure_kind = _first(
        safety.get("failure_kind"),
        contract.get("failure_kind"),
        failure.get("failure_type"),
        failure.get("failure_class"),
        default="unknown",
    )
    blocker = _first(
        failure.get("actual_failure"),
        failure.get("first_failing_line"),
        failure.get("headline_signal"),
        failure_kind,
        default="unknown failure",
    )
    owner = _first(
        safety.get("ownership_area"),
        contract.get("ownership_area"),
        failure.get("owner_hint"),
        _first_file(failure),
        default="unknown",
    )
    risk = _first(safety.get("risk"), failure.get("risk"), default="unknown")

    proof = list(_strings(safety.get("proof_commands")))
    repro = _text(failure.get("local_repro_command"))
    if repro and repro not in proof:
        proof.insert(0, repro)
    focused = tuple(proof[:1])
    quality = _dedupe((*proof[1:], *_strings(quality_proof_commands)))

    safe_fix = _bool(safety.get("safe_fix_allowed"))
    review_first = _bool(safety.get("review_first"), not safe_fix)
    proposal_ready = _proposal_ready(proposal_payload)
    verifier_state = _verifier_state(verifier_payload)
    status = _status(
        safe_fix=safe_fix,
        review_first=review_first,
        security_relevant=_bool(safety.get("security_relevance")),
        proposal_ready=proposal_ready,
        verifier_state=verifier_state,
    )

    allowed = ["inspect_evidence"]
    if focused:
        allowed.append("run_focused_proof")
    if quality:
        allowed.append("run_quality_proof")
    if safe_fix:
        allowed.append("prepare_patch_proposal")
    if proposal_ready:
        allowed.extend(("review_patch_proposal", "record_authenticated_decision"))
    if verifier_payload is not None:
        allowed.append("inspect_verifier_result")

    digests = {
        "failure_vector": _digest(failure),
        "safety_gate": _digest(safety),
    }
    if proposal_payload is not None:
        digests["proposal"] = _digest(proposal_payload)
    if verifier_payload is not None:
        digests["verifier"] = _digest(verifier_payload)
    for key, value in (evidence_digests or {}).items():
        name = str(key).strip()
        if not name or name in digests:
            raise ValueError(f"evidence digest {name!r} is computed and cannot be overridden")
        digests[name] = str(value).strip().lower()
    _validate_digests(digests)

    authority = {field: False for field in AUTHORITY_FIELDS}
    proposal_summary = _proposal_summary(proposal_payload)
    blocked_actions = _dedupe((*_strings(safety.get("blocked_actions")), *BLOCKED_ACTIONS))
    next_human_action = _next_action(proposal_ready, safe_fix, safety, contract)
    confidence = _confidence(failure_kind, blocker, owner, proof)
    common = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "commit_sha": commit_sha,
        "status": status,
        "primary_blocker": blocker,
        "failure_vector": failure,
        "owner_surface": owner,
        "confidence": confidence,
        "risk": risk,
        "authority": authority,
        "allowed_actions": tuple(allowed),
        "blocked_actions": blocked_actions,
        "proposed_change": proposal_summary,
        "focused_proof": focused,
        "quality_proof": quality,
        "verifier_state": verifier_state,
        "next_human_action": next_human_action,
        "evidence_digests": digests,
    }
    decision_id = f"decision_{_digest(common)}"
    return DecisionEnvelope(
        repository=repository,
        commit_sha=commit_sha,
        status=status,
        primary_blocker=blocker,
        owner_surface=owner,
        confidence=confidence,
        risk=risk,
        allowed_actions=tuple(allowed),
        blocked_actions=blocked_actions,
        focused_proof=focused,
        quality_proof=quality,
        verifier_state=verifier_state,
        next_human_action=next_human_action,
        decision_id=decision_id,
        _failure_vector_json=_canonical_json(failure),
        _authority_json=_canonical_json(authority),
        _proposed_change_json=(
            _canonical_json(proposal_summary) if proposal_summary is not None else None
        ),
        _evidence_digests_json=_canonical_json(digests),
    )


def write_decision_envelope(envelope: DecisionEnvelope, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(envelope.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_decision_envelope_markdown(envelope: DecisionEnvelope) -> str:
    values = (
        ("schema_version", envelope.schema_version),
        ("decision_id", envelope.decision_id),
        ("repository", envelope.repository),
        ("commit_sha", envelope.commit_sha),
        ("status", envelope.status),
        ("primary_blocker", envelope.primary_blocker),
        ("owner_surface", envelope.owner_surface),
        ("confidence", envelope.confidence),
        ("risk", envelope.risk),
        ("verifier_state", envelope.verifier_state),
        ("next_human_action", envelope.next_human_action),
    )
    lines = ["# SDETKit Decision Envelope", ""]
    lines.extend(f"- {name}: `{value}`" for name, value in values)
    lines.extend(("", "## Authority boundary", ""))
    lines.extend(f"- {field}: `false`" for field in AUTHORITY_FIELDS)
    return "\n".join((*lines, ""))


def _validate_identity(repository: str, commit_sha: str) -> None:
    parts = repository.split("/")
    if len(parts) != 2 or not all(parts) or repository != repository.strip():
        raise ValueError("repository must use owner/name form")
    if not _SHA_RE.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a lowercase 40- or 64-character hexadecimal SHA")


def _json_object(value: Mapping[str, Any], source: str) -> JsonObject:
    try:
        payload = json.loads(json.dumps(dict(value), sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source} must be JSON-serializable") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{source} must be a JSON object")
    return payload


def _optional_object(
    value: Mapping[str, Any] | None,
    source: str,
) -> JsonObject | None:
    return None if value is None else _json_object(value, source)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _decode_object(value: str) -> JsonObject:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("stored decision-envelope payload must decode to an object")
    return payload


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text or None


def _first(*values: object, default: str) -> str:
    return next((text for value in values if (text := _text(value))), default)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(text for item in value if (text := _text(item)))


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _iter_mappings(value: object) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for nested in value.values():
            yield from _iter_mappings(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _iter_mappings(nested)


def _assert_authority_denied(payload: Mapping[str, Any], source: str) -> None:
    expanded = sorted(
        {
            field
            for candidate in _iter_mappings(payload)
            for field in AUTHORITY_ALIASES
            if _bool(candidate.get(field))
        }
    )
    if expanded:
        raise ValueError(f"{source} expands authority: {', '.join(expanded)}")


def _assert_exact_head(
    payload: Mapping[str, Any],
    repository: str,
    commit_sha: str,
    source: str,
) -> None:
    if _text(payload.get("source_repository")) != repository:
        raise ValueError(f"{source} source_repository is not bound to the decision repository")
    if _text(payload.get("source_commit_sha")) != commit_sha:
        raise ValueError(f"{source} source_commit_sha is not bound to the decision head")


def _first_file(failure: Mapping[str, Any]) -> str | None:
    files = _strings(failure.get("affected_files"))
    return files[0] if files else None


def _proposal_ready(proposal: Mapping[str, Any] | None) -> bool:
    return bool(
        proposal
        and _text(proposal.get("status")) == "passed"
        and _text(proposal.get("proposal_status")) in PROPOSAL_READY_STATUSES
        and _bool(proposal.get("proposal_eligible"))
        and not _bool(proposal.get("branch_execution_allowed"))
    )


def _proposal_summary(proposal: Mapping[str, Any] | None) -> JsonObject | None:
    if proposal is None:
        return None
    keys = (
        "status",
        "proposal_status",
        "proposal_eligible",
        "candidate_family",
        "source_repository",
        "source_commit_sha",
        "source_pr_number",
        "branch_execution_allowed",
    )
    return {key: proposal[key] for key in keys if key in proposal}


def _verifier_state(verifier: Mapping[str, Any] | None) -> str:
    if verifier is None:
        return "not_run"
    decision = _mapping(verifier.get("decision"))
    return _first(
        verifier.get("status"),
        verifier.get("protected_verifier_status"),
        decision.get("status"),
        default="unknown",
    )


def _status(
    *,
    safe_fix: bool,
    review_first: bool,
    security_relevant: bool,
    proposal_ready: bool,
    verifier_state: str,
) -> str:
    if security_relevant or review_first:
        return "review_required"
    if proposal_ready:
        return "proposal_ready"
    if verifier_state in {"verified", "passed"} and not safe_fix:
        return "verified"
    return "eligible_for_proposal" if safe_fix else "blocked"


def _confidence(
    failure_kind: str,
    blocker: str,
    owner: str,
    proof: Sequence[str],
) -> str:
    known = (
        failure_kind != "unknown",
        blocker not in {"unknown", "unknown failure"},
        owner != "unknown",
        bool(proof),
    )
    return "high" if all(known) else "medium" if any(known) else "low"


def _next_action(
    proposal_ready: bool,
    safe_fix: bool,
    safety: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> str:
    if proposal_ready:
        return "review the exact-head proposal and record an authenticated decision"
    if safe_fix:
        return "prepare a non-mutating patch proposal and review it"
    return _first(
        safety.get("recommended_next_human_action"),
        contract.get("recommended_next_human_action"),
        default="triage the primary blocker and rerun focused proof",
    )


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = _canonical_json(payload)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_digests(digests: Mapping[str, str]) -> None:
    if not digests:
        raise ValueError("evidence_digests must not be empty")
    for name, digest in digests.items():
        if not name or not _DIGEST_RE.fullmatch(digest):
            raise ValueError(f"evidence digest {name!r} must be lowercase SHA-256")
