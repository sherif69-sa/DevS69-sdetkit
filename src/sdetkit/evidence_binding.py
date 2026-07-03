from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .protected_proof_chain import COMMIT_RE, JSON_STAGES, STAGE_ORDER, build_protected_proof_chain

SCHEMA_VERSION = "sdetkit.evidence_binding.v1"
REPOSITORY_KEYS = ("repository_full_name", "repo_full_name", "repository")
REVISION_KEYS = ("current_head_sha", "source_head_sha", "head_sha", "commit_sha")


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _revision_matches(claim: str, expected: str) -> bool:
    normalized = claim.lower()
    if not COMMIT_RE.fullmatch(normalized):
        return False
    return (
        normalized == expected or normalized.startswith(expected) or expected.startswith(normalized)
    )


def _conflicts(
    payload: Mapping[str, object],
    *,
    repository: str,
    revision: str,
) -> list[str]:
    conflicts: list[str] = []
    for key in REPOSITORY_KEYS:
        claim = _text(payload.get(key))
        if claim and claim != repository:
            conflicts.append(f"{key}={claim}")
    for key in REVISION_KEYS:
        claim = _text(payload.get(key))
        if claim and not _revision_matches(claim, revision):
            conflicts.append(f"{key}={claim}")
    return conflicts


def validate_evidence_binding(
    *,
    repository: str,
    revision: str,
    artifacts: Mapping[str, str | Path],
) -> dict[str, object]:
    repository_text = repository.strip()
    revision_text = revision.strip().lower()
    conflicts: list[str] = []
    checked_stages: list[str] = []
    claim_count = 0

    for stage in STAGE_ORDER:
        if stage not in JSON_STAGES:
            continue
        path = Path(artifacts[stage])
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object: {path}")
        checked_stages.append(stage)
        claim_count += sum(
            1 for key in (*REPOSITORY_KEYS, *REVISION_KEYS) if _text(payload.get(key))
        )
        conflicts.extend(
            f"{stage}:{item}"
            for item in _conflicts(
                payload,
                repository=repository_text,
                revision=revision_text,
            )
        )

    if conflicts:
        raise ValueError("evidence binding conflict: " + ", ".join(conflicts))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "repository": repository_text,
        "revision": revision_text,
        "checked_stages": checked_stages,
        "claim_count": claim_count,
    }


def build_bound_proof_chain(
    *,
    repository: str,
    revision: str,
    artifacts: Mapping[str, str | Path],
) -> dict[str, object]:
    validate_evidence_binding(
        repository=repository,
        revision=revision,
        artifacts=artifacts,
    )
    return build_protected_proof_chain(
        repository=repository,
        commit_sha=revision,
        artifacts=artifacts,
    )
