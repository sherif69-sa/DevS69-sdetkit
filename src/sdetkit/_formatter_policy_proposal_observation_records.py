from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from sdetkit import _formatter_policy_proposal_observation_schema as schema
from sdetkit import formatter_policy_proposal

JsonObject = dict[str, Any]


def normalize_observations(
    source: Mapping[str, Any],
    contract: Mapping[str, Any],
    root: Path,
) -> tuple[list[JsonObject], list[str], list[str], list[dict[str, str]]]:
    decisions, outcomes, metrics, required = schema.validate_contract(contract)
    if source.get("schema_version") != schema.OBSERVATIONS_SCHEMA_VERSION:
        raise ValueError(
            f"observations schema_version must be {schema.OBSERVATIONS_SCHEMA_VERSION}"
        )
    raw_items = source.get("observations")
    if not isinstance(raw_items, list):
        raise ValueError("observations must be a list")
    metric_ids = [item["metric_id"] for item in metrics]
    normalized: list[JsonObject] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_items, 1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"observation {index} must be an object")
        missing = [field for field in required if field not in raw]
        if missing:
            raise ValueError(f"observation {index} missing: {','.join(missing)}")
        record = _normalize_record(raw, index, root, decisions, outcomes, metric_ids)
        observation_id = str(record["observation_id"])
        if observation_id in seen:
            raise ValueError(f"observation {index} has invalid observation_id")
        seen.add(observation_id)
        normalized.append(record)
    return (
        sorted(normalized, key=lambda item: str(item["observation_id"])),
        decisions,
        outcomes,
        metrics,
    )


def _normalize_record(
    raw: Mapping[str, Any],
    index: int,
    root: Path,
    decisions: list[str],
    outcomes: list[str],
    metric_ids: list[str],
) -> JsonObject:
    observation_id = schema.text(raw.get("observation_id"))
    if not observation_id:
        raise ValueError(f"observation {index} has invalid observation_id")
    proposal_name = schema.text(raw.get("proposal_path"))
    proposal_file = _proposal_path(root, proposal_name)
    proposal_digest = schema.text(raw.get("proposal_sha256")).lower()
    if re.fullmatch(r"[0-9a-f]{64}", proposal_digest) is None:
        raise ValueError(f"observation {observation_id} proposal_sha256 must be sha256")
    if schema.sha256(proposal_file) != proposal_digest:
        raise ValueError(f"observation {observation_id} proposal digest is stale")
    commit = schema.text(raw.get("source_commit_sha")).lower()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError(f"observation {observation_id} source_commit_sha must be 40 hex chars")
    pr_number = raw.get("source_pr_number")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
        raise ValueError(f"observation {observation_id} source_pr_number must be positive")
    decision = schema.text(raw.get("decision"))
    if decision not in decisions:
        raise ValueError(f"observation {observation_id} has unsupported decision {decision!r}")
    reviewed_at = schema.text(raw.get("reviewed_at"))
    _timestamp(reviewed_at, f"observation {observation_id} reviewed_at")
    record: JsonObject = {
        "observation_id": observation_id,
        "proposal_path": proposal_name,
        "proposal_sha256": proposal_digest,
        "source_commit_sha": commit,
        "source_pr_number": pr_number,
        "decision": decision,
        "reviewed_at": reviewed_at,
    }
    for field in ("source_repository", "reviewer_id", "decision_reason", "review_notes"):
        value = schema.text(raw.get(field))
        if not value:
            raise ValueError(f"observation {observation_id} field {field} must be non-empty")
        record[field] = value
    raw_outcomes = raw.get("metric_outcomes")
    if not isinstance(raw_outcomes, Mapping) or set(raw_outcomes) != set(metric_ids):
        raise ValueError(f"observation {observation_id} must contain every contracted metric")
    normalized_outcomes = {
        metric_id: schema.text(raw_outcomes.get(metric_id)) for metric_id in metric_ids
    }
    if any(value not in outcomes for value in normalized_outcomes.values()):
        raise ValueError(f"observation {observation_id} has an invalid metric outcome")
    record["metric_outcomes"] = normalized_outcomes
    _validate_proposal(schema.load_object(proposal_file, "formatter policy proposal"), record)
    return record


def _proposal_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("proposal_path must be repository-relative")
    unresolved = root / relative
    if unresolved.is_symlink():
        raise ValueError("proposal_path cannot use a symlink")
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("proposal_path must remain inside the repository root") from exc
    if not resolved.is_file():
        raise ValueError(f"proposal_path is missing: {value}")
    return resolved


def _timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")


def _validate_proposal(proposal: Mapping[str, Any], observation: Mapping[str, Any]) -> None:
    if proposal.get("schema_version") != formatter_policy_proposal.SCHEMA_VERSION:
        raise ValueError("unsupported formatter policy proposal schema")
    if proposal.get("candidate_family") != "formatter_only":
        raise ValueError("observation source must be a formatter_only proposal")
    if proposal.get("proposal_status") != "eligible_for_human_policy_proposal":
        raise ValueError("formatter proposal is not eligible for human policy review")
    if proposal.get("proposal_eligible") is not True or proposal.get("review_required") is not True:
        raise ValueError("formatter proposal must be eligible and review-required")
    for field in (
        "execution_eligible",
        "branch_execution_allowed",
        "safe_fix_allowed",
        "safety_gate_policy_changed",
    ):
        if proposal.get(field) is not False:
            raise ValueError("formatter proposal expands execution or safety policy")
    schema.assert_authority_denied(proposal, "formatter proposal")
    for field in ("source_repository", "source_commit_sha", "source_pr_number"):
        if proposal.get(field) != observation.get(field):
            raise ValueError(f"observation {field} does not match proposal evidence")
