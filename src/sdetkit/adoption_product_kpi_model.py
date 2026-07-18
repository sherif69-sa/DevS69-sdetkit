from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "sdetkit.adoption_product_kpi_report.v1"
CONTRACT_SCHEMA = "sdetkit.adoption_product_kpi_evidence.v1"
OBSERVATIONS_SCHEMA = "sdetkit.adoption_product_kpi_observations.v1"
DEFAULT_CONTRACT = "docs/contracts/adoption-product-kpi-evidence.v1.json"
GENERATOR_SOURCE = "src/sdetkit/adoption_product_kpi_model.py"
AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "publication_authorized",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
)
REPORT_RULES = {
    "authoritative_zero_after_collection_failure": False,
    "explicit_denominators_required": True,
    "missing_outcomes_inferred": False,
    "predictions_are_proof": False,
    "reviewed_observations_only": True,
    "source_provenance_required": True,
    "target_repo_mutation": False,
    "target_tests_executed_by_reporter": False,
    "unavailable_malformed_unsupported_retained": True,
}


def authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def load_object(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid JSON object: {resolved}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {resolved}")
    return payload


def _head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _schema(path: Path) -> str:
    try:
        return str(load_object(path).get("schema_version", "")).strip()
    except ValueError:
        return ""


def _display(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _digest_parts(parts: list[tuple[str, bytes]]) -> str:
    hasher = hashlib.sha256()
    for label, content in sorted(parts):
        label_bytes = label.encode("utf-8")
        hasher.update(len(label_bytes).to_bytes(8, "big"))
        hasher.update(label_bytes)
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def input_provenance(
    observations_json: str | Path,
    *,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    observations_path = Path(observations_json).resolve()
    contract_path = Path(contract_json).resolve()
    generator = Path(generator_path).resolve() if generator_path else Path(__file__).resolve()
    head_sha = _head(repo_root) if current_head_sha is None else current_head_sha
    observations_bytes = observations_path.read_bytes() if observations_path.is_file() else b"<missing>"
    contract_bytes = contract_path.read_bytes() if contract_path.is_file() else b"<missing>"
    generator_bytes = generator.read_bytes() if generator.is_file() else b"<missing>"
    parts = [
        ("contract_schema", CONTRACT_SCHEMA.encode()),
        ("observations_schema", OBSERVATIONS_SCHEMA.encode()),
        ("current_head_sha", head_sha.encode()),
        ("report_schema", REPORT_SCHEMA.encode()),
        (GENERATOR_SOURCE, generator_bytes),
        ("contract_json", contract_bytes),
        ("observations_json", observations_bytes),
    ]
    return {
        "digest_algorithm": "sha256",
        "input_digest": _digest_parts(parts),
        "input_count": len(parts),
        "generator_schema_version": REPORT_SCHEMA,
        "generator_source": GENERATOR_SOURCE,
        "contract_path": _display(repo_root, contract_path),
        "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
        "contract_schema_version": _schema(contract_path),
        "observations_path": _display(repo_root, observations_path),
        "observations_sha256": hashlib.sha256(observations_bytes).hexdigest(),
        "observations_schema_version": _schema(observations_path),
        "accepted_contract_schema": CONTRACT_SCHEMA,
        "accepted_observations_schema": OBSERVATIONS_SCHEMA,
        "current_head_sha": head_sha,
        "current_head_available": bool(head_sha),
    }


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def metric_definitions(contract: dict[str, Any]) -> list[dict[str, str]]:
    raw = contract.get("metric_definitions")
    if not isinstance(raw, list) or not raw:
        raise ValueError("metric_definitions must be a non-empty list")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("metric definitions must be objects")
        metric_id = str(item.get("metric_id", "")).strip()
        description = str(item.get("description", "")).strip()
        if not metric_id or metric_id in seen or not description:
            raise ValueError("metric definitions require unique ids and descriptions")
        if item.get("numerator") != "reviewed_pass_observations":
            raise ValueError(f"unsupported numerator for {metric_id}")
        if item.get("denominator") != "reviewed_applicable_observations":
            raise ValueError(f"unsupported denominator for {metric_id}")
        seen.add(metric_id)
        result.append(
            {
                "metric_id": metric_id,
                "description": description,
                "numerator": "reviewed_pass_observations",
                "denominator": "reviewed_applicable_observations",
            }
        )
    return result


def _reviewed_at(value: str, observation_id: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"observation {observation_id} reviewed_at must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"observation {observation_id} reviewed_at must include timezone")


def reviewed_observations(
    source: dict[str, Any], contract: dict[str, Any], metric_ids: list[str]
) -> list[dict[str, Any]]:
    if source.get("schema_version") != OBSERVATIONS_SCHEMA:
        raise ValueError(f"observations schema_version must be {OBSERVATIONS_SCHEMA}")
    required = _string_list(contract.get("required_observation_fields"), "required fields")
    allowed = set(_string_list(contract.get("allowed_observation_outcomes"), "outcomes"))
    raw_items = source.get("observations")
    if not isinstance(raw_items, list):
        raise ValueError("observations must be a list")
    expected_metrics = set(metric_ids)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    text_fields = (
        "repository_name",
        "repository_url",
        "source_commit_sha",
        "evidence_path",
        "evidence_sha256",
        "reviewer_id",
        "reviewed_at",
        "review_notes",
    )
    for index, raw in enumerate(raw_items, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"observation {index} must be an object")
        missing = [field for field in required if field not in raw]
        if missing:
            raise ValueError(f"observation {index} missing: {','.join(missing)}")
        observation_id = str(raw.get("observation_id", "")).strip()
        if not observation_id or observation_id in seen:
            raise ValueError(f"observation {index} has invalid observation_id")
        seen.add(observation_id)
        normalized: dict[str, Any] = {"observation_id": observation_id}
        for field in text_fields:
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"observation {observation_id} field {field} must be non-empty")
            normalized[field] = value.strip()
        if re.fullmatch(r"[0-9a-fA-F]{7,64}", normalized["source_commit_sha"]) is None:
            raise ValueError(f"observation {observation_id} source_commit_sha must be hexadecimal")
        if re.fullmatch(r"[0-9a-fA-F]{64}", normalized["evidence_sha256"]) is None:
            raise ValueError(f"observation {observation_id} evidence_sha256 must be sha256")
        _reviewed_at(normalized["reviewed_at"], observation_id)
        outcomes = raw.get("metric_outcomes")
        if not isinstance(outcomes, dict) or set(outcomes) != expected_metrics:
            raise ValueError(f"observation {observation_id} must contain every contracted metric")
        normalized_outcomes: dict[str, str] = {}
        for metric_id in metric_ids:
            outcome = str(outcomes[metric_id]).strip()
            if outcome not in allowed:
                raise ValueError(f"observation {observation_id} has invalid outcome {outcome!r}")
            normalized_outcomes[metric_id] = outcome
        normalized["metric_outcomes"] = normalized_outcomes
        result.append(normalized)
    return sorted(result, key=lambda item: item["observation_id"])


def build_report(
    observations_json: str | Path,
    *,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    contract = load_object(contract_json)
    source = load_object(observations_json)
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError(f"contract schema_version must be {CONTRACT_SCHEMA}")
    definitions = metric_definitions(contract)
    metric_ids = [item["metric_id"] for item in definitions]
    observations = reviewed_observations(source, contract, metric_ids)
    outcomes = _string_list(contract.get("allowed_observation_outcomes"), "outcomes")
    provenance = input_provenance(
        observations_json,
        contract_json=contract_json,
        root=root,
        current_head_sha=current_head_sha,
        generator_path=generator_path,
    )
    metrics: list[dict[str, Any]] = []
    totals: Counter[str] = Counter({outcome: 0 for outcome in outcomes})
    unavailable_metrics: list[str] = []
    for definition in definitions:
        metric_id = definition["metric_id"]
        counts: Counter[str] = Counter({outcome: 0 for outcome in outcomes})
        for observation in observations:
            outcome = observation["metric_outcomes"][metric_id]
            counts[outcome] += 1
            totals[outcome] += 1
        numerator = counts["pass"]
        denominator = counts["pass"] + counts["fail"]
        if denominator == 0:
            unavailable_metrics.append(metric_id)
        metrics.append(
            {
                **definition,
                "status": "measured" if denominator else "unavailable",
                "reviewed_pass_observations": numerator,
                "reviewed_applicable_observations": denominator,
                "precision": round(numerator / denominator, 6) if denominator else None,
                "outcome_counts": {outcome: counts[outcome] for outcome in outcomes},
            }
        )
    boundary = authority_boundary()
    status = "reviewed_evidence_available" if observations and not unavailable_metrics else "review_required"
    return {
        "schema_version": REPORT_SCHEMA,
        "report_status": status,
        "input_provenance": provenance,
        "source_relationships": {
            "contract_schema_accepted": provenance["contract_schema_version"] == CONTRACT_SCHEMA,
            "observations_schema_accepted": provenance["observations_schema_version"]
            == OBSERVATIONS_SCHEMA,
            "current_head_bound": bool(provenance["current_head_available"]),
        },
        "reviewed_observation_count": len(observations),
        "metric_count": len(metrics),
        "metrics": metrics,
        "metrics_without_applicable_denominator": unavailable_metrics,
        "outcome_totals": {outcome: totals[outcome] for outcome in outcomes},
        "reviewed_observation_index": [
            {field: observation[field] for field in (
                "observation_id",
                "repository_name",
                "repository_url",
                "source_commit_sha",
                "evidence_path",
                "evidence_sha256",
                "reviewer_id",
                "reviewed_at",
            )}
            for observation in observations
        ],
        "rules": dict(REPORT_RULES),
        "authority_boundary": boundary,
        **boundary,
    }
