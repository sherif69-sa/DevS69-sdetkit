from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

SCHEMA_VERSION = "sdetkit.protected_proof_chain.v1"
VERIFICATION_SCHEMA_VERSION = "sdetkit.protected_proof_chain_verification.v1"
STATUS = "bound_review_first"

STAGE_ORDER = (
    "diagnostic_job",
    "failure_vector",
    "safety_gate",
    "proof_result",
    "verifier_result",
    "patch_score",
    "pr_report",
    "trajectory",
)
JSON_STAGES = frozenset(stage for stage in STAGE_ORDER if stage != "pr_report")
AUTHORITY_KEYS = frozenset(
    {
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "semantic_equivalence_claim",
        "security_dismissal_allowed",
        "automatic_security_fix_allowed",
        "automatic_dismissal_allowed",
        "security_dismissal",
    }
)
ENABLED_TEXT = frozenset(
    {
        "1",
        "allow",
        "allowed",
        "authorize",
        "authorized",
        "enable",
        "enabled",
        "proven",
        "true",
        "yes",
    }
)
REPOSITORY_RE = re.compile(r"^[^\s/]+/[^\s/]+$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
MARKDOWN_AUTHORITY_RE = re.compile(
    rf"(?im)^\s*(?:[-*]\s*)?(?P<key>{'|'.join(sorted(AUTHORITY_KEYS))})"
    r"\s*[:=]\s*(?P<value>[^\n]+)$"
)
REPOSITORY_IDENTITY_KEYS = (
    "repository_full_name",
    "repo_full_name",
    "repository",
)
COMMIT_IDENTITY_KEYS = (
    "current_head_sha",
    "source_head_sha",
    "head_sha",
    "commit_sha",
)

DECISION_BOUNDARY: dict[str, bool] = {
    "automation_allowed": False,
    "patch_application_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
    "security_dismissal_allowed": False,
}
SEPARATION_OF_DUTIES: dict[str, object] = {
    "worker_result_stage": "proof_result",
    "independent_verifier_stage": "verifier_result",
    "worker_may_self_certify": False,
    "verifier_result_required": True,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _authority_enabled(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().strip("`'\"").lower() in ENABLED_TEXT
    return False


def _json_violations(value: object, location: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key in AUTHORITY_KEYS and _authority_enabled(child):
                violations.append(child_location)
            violations.extend(_json_violations(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_json_violations(child, f"{location}[{index}]"))
    return violations


def _markdown_violations(text: str) -> list[str]:
    return [
        f"markdown:{match.group('key')}"
        for match in MARKDOWN_AUTHORITY_RE.finditer(text)
        if _authority_enabled(match.group("value"))
    ]


def _normalize_artifacts(artifacts: Mapping[str, str | Path]) -> dict[str, Path]:
    provided = set(artifacts)
    required = set(STAGE_ORDER)
    missing = sorted(required - provided)
    unexpected = sorted(provided - required)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise ValueError("invalid protected proof stages: " + "; ".join(details))

    normalized = {stage: Path(artifacts[stage]) for stage in STAGE_ORDER}
    absent = [stage for stage, path in normalized.items() if not path.is_file()]
    if absent:
        raise ValueError("missing protected proof artifact files: " + ", ".join(absent))
    return normalized


def _identity(repository: str, commit_sha: str) -> tuple[str, str]:
    repository_text = repository.strip()
    commit_text = commit_sha.strip()
    if not REPOSITORY_RE.fullmatch(repository_text):
        raise ValueError("repository identity must use owner/name form")
    if not COMMIT_RE.fullmatch(commit_text):
        raise ValueError("commit SHA must contain 7 to 64 hexadecimal characters")
    return repository_text, commit_text.lower()


def _identity_claim(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _commit_claim_matches(claim: str, expected: str) -> bool:
    normalized = claim.lower()
    if not COMMIT_RE.fullmatch(normalized):
        return False
    return (
        normalized == expected
        or normalized.startswith(expected)
        or expected.startswith(normalized)
    )


def _embedded_identity_violations(
    payload: Mapping[str, object],
    *,
    expected_repository: str,
    expected_commit_sha: str,
) -> list[str]:
    violations: list[str] = []
    for key in REPOSITORY_IDENTITY_KEYS:
        claim = _identity_claim(payload.get(key))
        if claim and claim != expected_repository:
            violations.append(f"{key}={claim}")
    for key in COMMIT_IDENTITY_KEYS:
        claim = _identity_claim(payload.get(key))
        if claim and not _commit_claim_matches(claim, expected_commit_sha):
            violations.append(f"{key}={claim}")
    return violations


def _entry(
    stage: str,
    path: Path,
    *,
    expected_repository: str,
    expected_commit_sha: str,
) -> tuple[dict[str, object], list[str], list[str]]:
    data = path.read_bytes()
    entry: dict[str, object] = {
        "stage": stage,
        "artifact_name": path.name,
        "sha256": _sha256(data),
        "size_bytes": len(data),
        "media_type": "application/json" if stage in JSON_STAGES else "text/markdown",
    }
    identity_violations: list[str] = []
    if stage in JSON_STAGES:
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError(
                f"expected JSON object for protected proof artifact: {path}"
            )
        entry["artifact_schema_version"] = str(
            payload.get("schema_version") or "unknown"
        )
        authority_violations = _json_violations(payload)
        identity_violations = _embedded_identity_violations(
            payload,
            expected_repository=expected_repository,
            expected_commit_sha=expected_commit_sha,
        )
    else:
        entry["artifact_schema_version"] = "markdown"
        authority_violations = _markdown_violations(
            data.decode("utf-8", errors="replace")
        )
    entry["authority_violation_count"] = len(authority_violations)
    return entry, authority_violations, identity_violations


def _material(
    repository: str,
    commit_sha: str,
    entries: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "repository": repository,
        "commit_sha": commit_sha,
        "stage_order": list(STAGE_ORDER),
        "entries": entries,
        "separation_of_duties": dict(SEPARATION_OF_DUTIES),
        "decision_boundary": dict(DECISION_BOUNDARY),
    }


def build_protected_proof_chain(
    *,
    repository: str,
    commit_sha: str,
    artifacts: Mapping[str, str | Path],
) -> dict[str, object]:
    repository_text, commit_text = _identity(repository, commit_sha)
    normalized = _normalize_artifacts(artifacts)
    entries: list[dict[str, object]] = []
    authority_violations: list[str] = []
    identity_violations: list[str] = []
    for stage in STAGE_ORDER:
        entry, stage_authority, stage_identity = _entry(
            stage,
            normalized[stage],
            expected_repository=repository_text,
            expected_commit_sha=commit_text,
        )
        entries.append(entry)
        authority_violations.extend(f"{stage}:{item}" for item in stage_authority)
        identity_violations.extend(f"{stage}:{item}" for item in stage_identity)
    if authority_violations:
        raise ValueError(
            "protected proof artifacts attempted to expand authority: "
            + ", ".join(authority_violations)
        )
    if identity_violations:
        raise ValueError(
            "protected proof artifact identity mismatch: "
            + ", ".join(identity_violations)
        )
    material = _material(repository_text, commit_text, entries)
    return {**material, "chain_id": _sha256(_canonical_json(material))}


def verify_protected_proof_chain(
    manifest: Mapping[str, object],
    *,
    artifacts: Mapping[str, str | Path],
    expected_repository: str,
    expected_commit_sha: str,
) -> dict[str, object]:
    repository_text, commit_text = _identity(expected_repository, expected_commit_sha)
    rebuilt = build_protected_proof_chain(
        repository=repository_text,
        commit_sha=commit_text,
        artifacts=artifacts,
    )
    fields = (
        "schema_version",
        "status",
        "repository",
        "commit_sha",
        "stage_order",
        "entries",
        "separation_of_duties",
        "decision_boundary",
        "chain_id",
    )
    mismatches = [
        {
            "stage": f"manifest.{field}",
            "expected": rebuilt[field],
            "actual": manifest.get(field),
        }
        for field in fields
        if manifest.get(field) != rebuilt[field]
    ]
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "ok": not mismatches,
        "chain_id": str(manifest.get("chain_id") or ""),
        "mismatches": mismatches,
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def write_protected_proof_chain(
    payload: Mapping[str, object],
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_protected_proof_chain(payload), encoding="utf-8")


def render_protected_proof_chain(payload: Mapping[str, object]) -> str:
    entries = payload.get("entries")
    safe_entries = entries if isinstance(entries, list) else []
    lines = [
        "# Protected proof chain",
        "",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- repository: `{payload.get('repository', 'unknown')}`",
        f"- commit_sha: `{payload.get('commit_sha', 'unknown')}`",
        f"- chain_id: `{payload.get('chain_id', 'unknown')}`",
        "- automation_allowed: `false`",
        "- patch_application_allowed: `false`",
        "- merge_authorized: `false`",
        "- semantic_equivalence_proven: `false`",
        "",
        "## Bound stages",
        "",
    ]
    for entry in safe_entries:
        if isinstance(entry, dict):
            lines.append(
                f"- `{entry.get('stage', 'unknown')}`: `{entry.get('sha256', 'unknown')}` "
                f"({entry.get('size_bytes', 0)} bytes)"
            )
    lines.extend(
        [
            "",
            "The worker proof result and protected verifier result are separate bound stages.",
            "This manifest records evidence identity only; it does not authorize a patch or merge.",
            "",
        ]
    )
    return "\n".join(lines)
