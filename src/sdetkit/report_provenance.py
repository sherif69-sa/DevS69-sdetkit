from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

FRESHNESS_AUTHORITY_BOUNDARY = {
    "reporting_only": True,
    "repo_mutation": False,
    "issue_mutation_allowed": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

_PROVENANCE_MATCH_FIELDS = (
    "digest_algorithm",
    "input_digest",
    "input_count",
    "generator_schema_version",
    "generator_source",
    "generator_sha256",
    "generated_from_head_sha",
    "source_issue_count",
    "source_issue_numbers",
    "source_run_ids",
    "input_digests",
    "input_artifact_schemas",
)


def _update_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def normalize_int_ids(values: Iterable[object]) -> list[int]:
    normalized: set[int] = set()
    for value in values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            normalized.add(number)
    return sorted(normalized)


def extract_source_issue_numbers(issues: Sequence[Mapping[str, Any]]) -> list[int]:
    values: list[object] = []
    for issue in issues:
        values.append(issue.get("issue_number", issue.get("number")))
    return normalize_int_ids(values)


def collect_source_run_ids(
    explicit: Iterable[object] = (),
    *,
    issues: Sequence[Mapping[str, Any]] = (),
    payloads: Sequence[Mapping[str, Any]] = (),
) -> list[int]:
    values: list[object] = list(explicit)
    for issue in issues:
        for key in ("source_run_id", "workflow_run_id", "run_id"):
            values.append(issue.get(key))
    for payload in payloads:
        raw = payload.get("source_run_ids", [])
        if isinstance(raw, list):
            values.extend(raw)
        provenance = payload.get("input_provenance")
        if isinstance(provenance, dict):
            raw = provenance.get("source_run_ids", [])
            if isinstance(raw, list):
                values.extend(raw)
    return normalize_int_ids(values)


def resolve_current_head(
    root: str | Path,
    *,
    override: str | None = None,
) -> str:
    if override is not None:
        value = override.strip().lower()
    else:
        completed = subprocess.run(
            ["git", "-C", str(Path(root)), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = completed.stdout.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError(f"current Git head must be a full SHA-1, got {value!r}")
    return value


def normalize_generated_at(value: str | None = None) -> str:
    if value is None:
        return (
            dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("generated_at must include a timezone")
    return (
        parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def build_input_provenance(
    *,
    schema_version: str,
    generator_source: str,
    generator_bytes: bytes,
    data_inputs: Mapping[str, bytes],
    root: str | Path,
    source_issue_numbers: Iterable[object],
    source_run_ids: Iterable[object] = (),
    input_artifact_schemas: Mapping[str, str] | None = None,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    issue_numbers = normalize_int_ids(source_issue_numbers)
    run_ids = normalize_int_ids(source_run_ids)
    artifact_schemas = dict(sorted((input_artifact_schemas or {}).items()))
    head = resolve_current_head(root, override=current_head_sha)
    generated = normalize_generated_at(generated_at)

    input_digests = {
        label: hashlib.sha256(content).hexdigest() for label, content in sorted(data_inputs.items())
    }
    generator_sha256 = hashlib.sha256(generator_bytes).hexdigest()

    digest_inputs: dict[str, bytes] = {
        "schema_version": schema_version.encode("utf-8"),
        "generator_source": generator_bytes,
        "current_head_sha": head.encode("utf-8"),
        "source_issue_numbers": json.dumps(issue_numbers, separators=(",", ":")).encode("utf-8"),
        "source_run_ids": json.dumps(run_ids, separators=(",", ":")).encode("utf-8"),
        "input_artifact_schemas": json.dumps(
            artifact_schemas,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        **data_inputs,
    }
    hasher = hashlib.sha256()
    for label, content in sorted(digest_inputs.items()):
        _update_digest(hasher, label, content)

    return {
        "digest_algorithm": "sha256",
        "input_digest": hasher.hexdigest(),
        "input_count": len(digest_inputs),
        "generator_schema_version": schema_version,
        "generator_source": generator_source,
        "generator_sha256": generator_sha256,
        "generated_at": generated,
        "generated_from_head_sha": head,
        "source_issue_count": len(issue_numbers),
        "source_issue_numbers": issue_numbers,
        "source_run_ids": run_ids,
        "input_digests": input_digests,
        "input_artifact_schemas": artifact_schemas,
    }


def attach_provenance(
    payload: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(payload)
    result.update(
        {
            "generated_at": provenance["generated_at"],
            "current_head_sha": provenance["generated_from_head_sha"],
            "source_issue_numbers": list(provenance["source_issue_numbers"]),
            "source_run_ids": list(provenance["source_run_ids"]),
            "input_digests": dict(provenance["input_digests"]),
            "input_provenance": dict(provenance),
        }
    )
    return result


def _valid_generated_at(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        normalize_generated_at(value)
    except (TypeError, ValueError):
        return False
    return True


def evaluate_report_freshness(
    payload: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    expected_schema_version: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if payload.get("schema_version") != expected_schema_version:
        reasons.append("report_schema_version_mismatch")

    recorded = payload.get("input_provenance")
    if not isinstance(recorded, dict):
        recorded = {}
        reasons.append("missing_input_provenance")

    for field in _PROVENANCE_MATCH_FIELDS:
        if recorded.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    if not _valid_generated_at(recorded.get("generated_at")):
        reasons.append("generated_at_invalid")

    mirrors = {
        "generated_at": recorded.get("generated_at"),
        "current_head_sha": current.get("generated_from_head_sha"),
        "source_issue_numbers": current.get("source_issue_numbers"),
        "source_run_ids": current.get("source_run_ids"),
        "input_digests": current.get("input_digests"),
    }
    for field, expected in mirrors.items():
        if payload.get(field) != expected:
            reasons.append(f"{field}_mismatch")

    reasons = sorted(set(reasons))
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "reasons": reasons,
        "recorded_input_digest": recorded.get("input_digest", ""),
        "current_input_digest": current.get("input_digest", ""),
        "recorded_head_sha": recorded.get("generated_from_head_sha", ""),
        "current_head_sha": current.get("generated_from_head_sha", ""),
        "recorded_generated_at": recorded.get("generated_at", ""),
        **FRESHNESS_AUTHORITY_BOUNDARY,
    }


def check_report_path(
    report_path: str | Path,
    current: Mapping[str, Any],
    *,
    expected_schema_version: str,
) -> dict[str, Any]:
    path = Path(report_path)
    extra_reason = ""
    if not path.is_file():
        payload: Mapping[str, Any] = {}
        extra_reason = "report_missing"
    else:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
            extra_reason = "report_invalid_json"
        if isinstance(loaded, dict):
            payload = loaded
        else:
            payload = {}
            extra_reason = "report_invalid_type"

    result = evaluate_report_freshness(
        payload,
        current,
        expected_schema_version=expected_schema_version,
    )
    if extra_reason:
        result["reasons"] = sorted(set([*result["reasons"], extra_reason]))
        result["status"] = "stale"
        result["fresh"] = False
    return result


def render_freshness_text(payload: Mapping[str, Any]) -> str:
    reasons = payload.get("reasons", [])
    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "none"
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"freshness_reasons={reason_text}",
            f"recorded_input_digest={payload.get('recorded_input_digest', '')}",
            f"current_input_digest={payload.get('current_input_digest', '')}",
            f"recorded_head_sha={payload.get('recorded_head_sha', '')}",
            f"current_head_sha={payload.get('current_head_sha', '')}",
            "reporting_only=true",
            "repo_mutation=false",
            "issue_mutation_allowed=false",
            "automation_allowed=false",
            "patch_application_allowed=false",
            "security_dismissal_allowed=false",
            "merge_authorized=false",
            "semantic_equivalence_proven=false",
        ]
    )
