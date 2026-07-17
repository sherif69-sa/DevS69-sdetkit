from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sdetkit.failure_vector import BUNDLE_SCHEMA_VERSION, FailureVector
from sdetkit.failure_vector_adapters import (
    FailureVectorAdapterResult,
    extract_ecosystem_failure_vector,
)
from sdetkit.protected_verifier import verify_patch
from sdetkit.safety_gate import SafetyGateDecision, evaluate_failure_vector

SCHEMA_VERSION = "sdetkit.workspace_failure_ownership.v1"
DEFAULT_ENVIRONMENT = "github_actions"

JsonObject = dict[str, Any]

_AUTHORITY_BOUNDARY: JsonObject = {
    "target_code_execution": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "publication_authorized": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


@dataclass(frozen=True, order=True)
class WorkspaceDefinition:
    path: str
    ecosystem: str
    manifest: str

    def normalized(self) -> WorkspaceDefinition:
        path = _normalize_workspace_path(self.path)
        manifest = _normalize_evidence_path(self.manifest)
        if not path or path == ".":
            raise ValueError("workspace path must identify a nested repository-owned workspace")
        if not self.ecosystem.strip():
            raise ValueError("workspace ecosystem must be non-empty")
        if not manifest:
            raise ValueError("workspace manifest must be non-empty")
        return WorkspaceDefinition(path, self.ecosystem.strip(), manifest)

    def to_dict(self) -> dict[str, str]:
        return asdict(self.normalized())


@dataclass(frozen=True)
class WorkspaceFailureResult:
    workspace: WorkspaceDefinition | None
    candidate_workspaces: tuple[WorkspaceDefinition, ...]
    evidence_source: str
    ownership_confidence: str
    adapter: FailureVectorAdapterResult
    safety_gate: SafetyGateDecision
    protected_verifier: Mapping[str, Any]
    uncertainty: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        workspace_payload = (
            self.workspace.to_dict() if self.workspace is not None else _unknown_workspace()
        )
        vector_payload = self.adapter.to_dict()
        vector_payload.update(
            {
                "workspace_identity": workspace_payload,
                "evidence_source": self.evidence_source,
                "ownership_confidence": self.ownership_confidence,
                "identity_key": _identity_key(workspace_payload, self.evidence_source),
            }
        )
        safety_payload = self.safety_gate.to_dict()
        safety_payload.update(
            {
                "workspace_identity": workspace_payload,
                "evidence_source": self.evidence_source,
            }
        )
        protected_payload = dict(self.protected_verifier)
        protected_payload.update(
            {
                "workspace_identity": workspace_payload,
                "evidence_source": self.evidence_source,
                "synthetic_patch_created": False,
            }
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "review_required",
            "workspace_identity": workspace_payload,
            "candidate_workspaces": [item.to_dict() for item in self.candidate_workspaces],
            "evidence_source": self.evidence_source,
            "identity_key": _identity_key(workspace_payload, self.evidence_source),
            "ownership_confidence": self.ownership_confidence,
            "uncertainty": list(self.uncertainty),
            "failure_vector": vector_payload,
            "safety_gate": safety_payload,
            "protected_verifier": protected_payload,
            "review_first": self.safety_gate.review_first
            and _protected_review_first(protected_payload),
            "target_code_execution": False,
            "synthetic_patch_created": False,
            "authority_boundary": dict(_AUTHORITY_BOUNDARY),
        }


def normalize_saved_workspace_failure(
    log_text: str,
    *,
    workspaces: Sequence[WorkspaceDefinition],
    evidence_source: str,
    check: str,
    environment: str = DEFAULT_ENVIRONMENT,
) -> WorkspaceFailureResult:
    """Normalize saved evidence while preserving or denying workspace ownership explicitly."""

    normalized_workspaces = _normalized_workspaces(workspaces)
    source = _normalize_evidence_path(evidence_source)
    if not source:
        raise ValueError("evidence_source must be non-empty")
    candidates = tuple(
        workspace
        for workspace in normalized_workspaces
        if _mentions_workspace(log_text, workspace.path)
    )

    if len(candidates) == 1:
        workspace = candidates[0]
        adapter = extract_ecosystem_failure_vector(
            log_text,
            ecosystem=workspace.ecosystem,
            check=check,
            log_url=source,
            environment=environment,
        )
        uncertainty = tuple(adapter.uncertainty)
        confidence = "high" if adapter.confidence != "low" else "low"
    else:
        workspace = None
        reasons = (
            ("workspace_not_identified",)
            if not candidates
            else ("multiple_workspace_candidates:" + ",".join(item.path for item in candidates),)
        )
        adapter = _ambiguous_adapter_result(
            log_text,
            check=check,
            log_url=source,
            environment=environment,
            uncertainty=reasons,
        )
        uncertainty = reasons
        confidence = "low"

    safety_gate = evaluate_failure_vector(adapter.vector)
    failure_bundle = _failure_bundle(
        adapter,
        workspace=workspace,
        candidate_workspaces=candidates,
        evidence_source=source,
        environment=environment,
        safety_gate=safety_gate,
    )
    protected_verifier = verify_patch(
        patch_score={},
        failure_bundle=failure_bundle,
    )
    return WorkspaceFailureResult(
        workspace=workspace,
        candidate_workspaces=candidates,
        evidence_source=source,
        ownership_confidence=confidence,
        adapter=adapter,
        safety_gate=safety_gate,
        protected_verifier=protected_verifier,
        uncertainty=uncertainty,
    )


def build_workspace_failure_bundle(
    log_paths: Sequence[str | Path],
    *,
    workspaces: Sequence[WorkspaceDefinition],
    evidence_root: str | Path | None = None,
    environment: str = DEFAULT_ENVIRONMENT,
) -> JsonObject:
    """Build deterministic workspace-scoped FailureVector evidence from saved log files."""

    root = Path(evidence_root).resolve() if evidence_root is not None else None
    entries: list[JsonObject] = []
    for path in sorted((Path(item) for item in log_paths), key=lambda item: item.as_posix()):
        if not path.is_file():
            raise ValueError(f"saved failure log does not exist: {path}")
        source = _relative_evidence_source(path, root)
        result = normalize_saved_workspace_failure(
            path.read_text(encoding="utf-8", errors="ignore"),
            workspaces=workspaces,
            evidence_source=source,
            check=path.stem,
            environment=environment,
        )
        entries.append(result.to_dict())

    entries.sort(key=lambda item: str(item["identity_key"]))
    identity_keys = [str(item["identity_key"]) for item in entries]
    if len(identity_keys) != len(set(identity_keys)):
        raise RuntimeError("workspace failure identity collision detected")

    by_workspace = Counter(str(item["workspace_identity"]["path"]) for item in entries)
    by_ecosystem = Counter(str(item["workspace_identity"]["ecosystem"]) for item in entries)
    return {
        "schema_version": SCHEMA_VERSION,
        "vector_bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "status": "review_required",
        "environment": environment,
        "failure_vector_count": len(entries),
        "summary": {
            "by_workspace": dict(sorted(by_workspace.items())),
            "by_ecosystem": dict(sorted(by_ecosystem.items())),
            "high_confidence_ownership_count": sum(
                1 for item in entries if item["ownership_confidence"] == "high"
            ),
            "low_confidence_ownership_count": sum(
                1 for item in entries if item["ownership_confidence"] == "low"
            ),
            "review_first_count": sum(1 for item in entries if item["review_first"] is True),
        },
        "workspace_failures": entries,
        "target_code_execution": False,
        "synthetic_patch_created": False,
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
    }


def _normalized_workspaces(
    workspaces: Sequence[WorkspaceDefinition],
) -> tuple[WorkspaceDefinition, ...]:
    normalized = tuple(sorted({item.normalized() for item in workspaces}))
    if not normalized:
        raise ValueError("at least one workspace definition is required")
    paths = [item.path for item in normalized]
    if len(paths) != len(set(paths)):
        raise ValueError("workspace paths must be unique")
    return normalized


def _normalize_workspace_path(path: str) -> str:
    normalized = _normalize_evidence_path(path).strip("/")
    return normalized or "."


def _normalize_evidence_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def _mentions_workspace(log_text: str, workspace: str) -> bool:
    normalized = log_text.replace("\\", "/")
    return f"{workspace.rstrip('/')}/" in normalized


def _relative_evidence_source(path: Path, root: Path | None) -> str:
    resolved = path.resolve()
    if root is None:
        return path.as_posix()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"saved failure log is outside evidence_root: {path}") from exc


def _ambiguous_adapter_result(
    log_text: str,
    *,
    check: str,
    log_url: str,
    environment: str,
    uncertainty: tuple[str, ...],
) -> FailureVectorAdapterResult:
    first_line = next(
        (line.strip() for line in log_text.splitlines() if line.strip()),
        "unknown",
    )
    vector = FailureVector(
        check=check,
        command="unknown",
        exit_code=None,
        failure_class="unknown",
        risk="high",
        scope="unknown",
        reproducible_locally="not_run",
        safe_fix_candidate=False,
        first_failing_line=first_line,
        affected_files=(),
        log_url=log_url,
        local_repro_command=None,
        environment=environment,
        headline_signal=f"{check}: ambiguous_workspace",
        actual_failure=first_line,
        failure_type="unknown",
        failing_command="unknown",
        failing_test_or_check=check,
        owner_hint="unknown",
        safe_fix_allowed=False,
    )
    return FailureVectorAdapterResult(
        vector=vector,
        ecosystem="unknown",
        tool="unknown",
        confidence="low",
        uncertainty=uncertainty,
    )


def _failure_bundle(
    adapter: FailureVectorAdapterResult,
    *,
    workspace: WorkspaceDefinition | None,
    candidate_workspaces: Sequence[WorkspaceDefinition],
    evidence_source: str,
    environment: str,
    safety_gate: SafetyGateDecision,
) -> JsonObject:
    workspace_payload = workspace.to_dict() if workspace is not None else _unknown_workspace()
    vector_payload = adapter.to_dict()
    vector_payload.update(
        {
            "workspace_identity": workspace_payload,
            "evidence_source": evidence_source,
        }
    )
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "status": "review_required",
        "environment": environment,
        "failure_vector_count": 1,
        "workspace_identity": workspace_payload,
        "candidate_workspaces": [item.to_dict() for item in candidate_workspaces],
        "evidence_source": evidence_source,
        "failure_vectors": [vector_payload],
        "safety_gate": {
            **safety_gate.to_dict(),
            "workspace_identity": workspace_payload,
            "evidence_source": evidence_source,
        },
        "target_code_execution": False,
        "synthetic_patch_created": False,
        "decision_boundary": dict(_AUTHORITY_BOUNDARY),
    }


def _unknown_workspace() -> dict[str, str]:
    return {"path": "unknown", "ecosystem": "unknown", "manifest": "unknown"}


def _identity_key(workspace: Mapping[str, Any], evidence_source: str) -> str:
    return "|".join(
        (
            str(workspace.get("path", "unknown")),
            str(workspace.get("ecosystem", "unknown")),
            evidence_source,
        )
    )


def _protected_review_first(payload: Mapping[str, Any]) -> bool:
    decision = payload.get("decision")
    return isinstance(decision, Mapping) and decision.get("review_first") is True


def render_workspace_failure_bundle(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
