from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit import formatter_policy_proposal

REPORT_SCHEMA_VERSION = "sdetkit.formatter_policy_proposal_observation_report.v1"
CONTRACT_SCHEMA_VERSION = "sdetkit.formatter_policy_proposal_observation_contract.v1"
OBSERVATIONS_SCHEMA_VERSION = "sdetkit.formatter_policy_proposal_observations.v1"
GENERATOR_SOURCE = "src/sdetkit/formatter_policy_proposal_observation.py"
JsonObject = dict[str, Any]
AUTHORITY_FIELDS = formatter_policy_proposal.AUTHORITY_FIELDS


def authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def load_object(path: Path, label: str) -> JsonObject:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid {label} JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected {label} JSON object: {path}")
    return payload


def text(value: object) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_head(root: Path, override: str | None) -> str:
    if override is None:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip().lower() if result.returncode == 0 else ""
    else:
        value = override.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("current Git head must be a 40-character hexadecimal SHA")
    return value


def assert_authority_denied(payload: Mapping[str, Any], source: str) -> None:
    expanded = [field for field in AUTHORITY_FIELDS if payload.get(field) is not False]
    if expanded:
        raise ValueError(f"{source} must explicitly deny authority: {', '.join(expanded)}")


def validate_contract(
    payload: Mapping[str, Any],
) -> tuple[list[str], list[str], list[dict[str, str]], list[str]]:
    if payload.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"contract schema_version must be {CONTRACT_SCHEMA_VERSION}")
    decisions = _string_list(payload.get("allowed_decisions"), "allowed_decisions")
    outcomes = _string_list(payload.get("allowed_metric_outcomes"), "allowed_metric_outcomes")
    if set(outcomes) != {"pass", "fail", "not_applicable"}:
        raise ValueError("allowed_metric_outcomes must be pass, fail, and not_applicable")
    boundary = payload.get("authority_boundary")
    if not isinstance(boundary, Mapping):
        raise ValueError("contract authority_boundary must be an object")
    assert_authority_denied(boundary, "observation contract")
    rules = payload.get("rules")
    required_false = (
        "branch_execution_allowed",
        "history_authorizes_current_action",
        "observations_are_authority",
        "target_repo_mutation",
        "broader_maturity_claim_allowed",
    )
    if not isinstance(rules, Mapping) or any(
        rules.get(field) is not False for field in required_false
    ):
        raise ValueError("observation rules must keep execution and authority disabled")
    raw_metrics = payload.get("metric_definitions")
    if not isinstance(raw_metrics, list) or not raw_metrics:
        raise ValueError("metric_definitions must be a non-empty list")
    metrics: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_metrics:
        if not isinstance(raw, Mapping):
            raise ValueError("metric definitions must be objects")
        metric_id = text(raw.get("metric_id"))
        description = text(raw.get("description"))
        if not metric_id or metric_id in seen or not description:
            raise ValueError("metric definitions require unique ids and descriptions")
        seen.add(metric_id)
        metrics.append({"metric_id": metric_id, "description": description})
    required = _string_list(payload.get("required_observation_fields"), "required fields")
    return decisions, outcomes, metrics, required


def input_provenance(
    root: Path,
    observations_path: Path,
    contract_path: Path,
    head: str,
    generator_path: Path,
) -> JsonObject:
    parts = {
        "current_head_sha": head.encode(),
        "report_schema": REPORT_SCHEMA_VERSION.encode(),
        "observations": observations_path.read_bytes(),
        "contract": contract_path.read_bytes(),
        "generator": generator_path.read_bytes(),
    }
    digest = hashlib.sha256()
    for label, content in sorted(parts.items()):
        digest.update(label.encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return {
        "digest_algorithm": "sha256",
        "input_digest": digest.hexdigest(),
        "input_count": len(parts),
        "current_head_sha": head,
        "generator_source": GENERATOR_SOURCE,
        "generator_schema_version": REPORT_SCHEMA_VERSION,
        "generator_sha256": sha256(generator_path),
        "contract_path": _display(root, contract_path),
        "contract_sha256": sha256(contract_path),
        "observations_path": _display(root, observations_path),
        "observations_sha256": sha256(observations_path),
    }


def _display(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    result = [item.strip() for item in value if item.strip()]
    if not result or len(result) != len(set(result)):
        raise ValueError(f"{field} must contain unique non-empty strings")
    return result
