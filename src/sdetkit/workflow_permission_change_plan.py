from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .workflow_permission_review_control_plane import build_workflow_permission_review_control_plane

SCHEMA_VERSION = "sdetkit.workflow_permission_change_plan.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-change-plan.v1.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_change_plan.py"
PLAN_DECISIONS = ("reduce", "split")
NON_CHANGE_DECISIONS = ("keep", "defer")
ALLOWED_PERMISSION_LEVELS = ("read", "write", "none")
DIGEST_ALGORITHM = "sha256"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "commit_allowed",
    "implementation_authorized",
    "merge_authorized",
    "patch_application_allowed",
    "permission_increase_allowed",
    "permission_mutation_allowed",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
    "source_tree_write_allowed",
    "workflow_mutation_allowed",
)


def authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _update_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def _decision_record_sha256(root: Path, record_ref: object) -> str | None:
    if not isinstance(record_ref, str) or not record_ref:
        return None
    path = root / record_ref
    if not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


def _plan_id(review_id: object) -> str:
    return f"wpcp-{review_id or 'unknown'}"


def _implementation_template() -> dict[str, Any]:
    return {
        "implementation_scope": "permissions_only",
        "top_level_permissions": None,
        "job_permissions": None,
        "implementation_rationale": None,
        "proof_execution_refs": [],
        "rollback_execution_ref": None,
        "human_completion_required": True,
    }


def _plan_digest(plan: dict[str, Any]) -> str:
    payload = dict(plan)
    payload.pop("plan_digest", None)
    return _sha256_bytes(_canonical_json_bytes(payload))


def _build_plan(root: Path, entry: dict[str, Any]) -> dict[str, Any] | None:
    decision = entry.get("human_decision")
    if decision not in PLAN_DECISIONS:
        return None
    record_ref = entry.get("decision_record_ref")
    record_sha256 = _decision_record_sha256(root, record_ref)
    if record_sha256 is None:
        return None

    write_scopes = sorted({str(scope) for scope in entry.get("granted_write_scopes", [])})
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": _plan_id(entry.get("review_id")),
        "review_id": entry.get("review_id"),
        "workflow": entry.get("workflow"),
        "workflow_sha256": entry.get("workflow_sha256"),
        "permission_group": entry.get("permission_group"),
        "decision_binding": {
            "decision": decision,
            "decision_record_ref": record_ref,
            "decision_record_sha256": record_sha256,
            "approved_intent": entry.get("proposed_change"),
        },
        "current_permission_snapshot": {
            "granted_write_scopes": write_scopes,
            "write_scope_count": len(write_scopes),
        },
        "implementation": _implementation_template(),
        "proof_contract": list(entry.get("proof_contract", [])),
        "rollback_contract": entry.get("rollback_contract"),
        "ready_for_patch": False,
        "safe_to_patch": False,
        "requires_separate_reviewed_pr": True,
        "authority_boundary": authority_boundary(),
    }
    plan["plan_digest"] = _plan_digest(plan)
    return plan


def workflow_permission_change_plan_input_provenance(
    repo_root: str | Path = ".",
    *,
    control_plane: dict[str, Any] | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    plane = control_plane or build_workflow_permission_review_control_plane(root)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator.read_bytes()),
        (
            "control_plane_input_digest",
            str(plane.get("input_provenance", {}).get("input_digest", "")).encode("utf-8"),
        ),
    ]
    contract = root / CONTRACT_PATH
    if contract.is_file():
        inputs.append((CONTRACT_PATH, contract.read_bytes()))

    hasher = hashlib.sha256()
    for label, content in sorted(inputs, key=lambda item: item[0]):
        _update_digest(hasher, label, content)
    return {
        "digest_algorithm": DIGEST_ALGORITHM,
        "input_digest": hasher.hexdigest(),
        "input_count": len(inputs),
        "control_plane_input_digest": plane.get("input_provenance", {}).get("input_digest", ""),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "contract_path": CONTRACT_PATH,
    }


def build_workflow_permission_change_plan_index(
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    plane = build_workflow_permission_review_control_plane(root)
    queue = plane.get("review_queue", [])
    if not isinstance(queue, list):
        queue = []

    plans: list[dict[str, Any]] = []
    non_change_decisions = 0
    pending_reviews = 0
    missing_record_bindings: list[str] = []
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        if entry.get("human_decision_recorded") is not True:
            pending_reviews += 1
            continue
        decision = entry.get("human_decision")
        if decision in NON_CHANGE_DECISIONS:
            non_change_decisions += 1
            continue
        if decision not in PLAN_DECISIONS:
            continue
        plan = _build_plan(root, entry)
        if plan is None:
            missing_record_bindings.append(str(entry.get("workflow", "unknown")))
            continue
        plans.append(plan)

    plans.sort(key=lambda item: str(item.get("workflow", "")))
    missing_record_bindings = sorted(set(missing_record_bindings))
    provenance = workflow_permission_change_plan_input_provenance(root, control_plane=plane)
    plan_refs = [
        {
            "plan_id": plan["plan_id"],
            "review_id": plan["review_id"],
            "workflow": plan["workflow"],
            "workflow_sha256": plan["workflow_sha256"],
            "decision": plan["decision_binding"]["decision"],
            "decision_record_ref": plan["decision_binding"]["decision_record_ref"],
            "decision_record_sha256": plan["decision_binding"]["decision_record_sha256"],
            "plan_digest": plan["plan_digest"],
        }
        for plan in plans
    ]
    bundle_digest = _sha256_bytes(_canonical_json_bytes({"plans": plan_refs}))

    if missing_record_bindings:
        status = "blocked"
    elif plans:
        status = "human_implementation_plan_required"
    else:
        status = "not_required"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "input_provenance": provenance,
        "summary": {
            "change_plan_count": len(plans),
            "reduce_or_split_decision_count": len(plans) + len(missing_record_bindings),
            "non_change_decision_count": non_change_decisions,
            "pending_human_review_count": pending_reviews,
            "missing_decision_record_binding_count": len(missing_record_bindings),
            "automatic_plan_completion_allowed": False,
            "automatic_patch_generation_allowed": False,
            "automatic_permission_change_allowed": False,
        },
        "missing_decision_record_bindings": missing_record_bindings,
        "bundle_digest": bundle_digest,
        "plan_index": plan_refs,
        "plans": plans,
        "rules": {
            "valid_current_human_decision_required": True,
            "only_reduce_or_split_create_plan": True,
            "keep_or_defer_create_no_change_plan": False,
            "generated_plan_may_not_infer_target_permissions": True,
            "separate_reviewed_permission_pr_required": True,
            "workflow_mutation_allowed": False,
        },
        "authority_boundary": authority_boundary(),
    }


def _normalize_permissions(value: object) -> tuple[dict[str, str] | None, list[str]]:
    if value is None:
        return None, []
    if not isinstance(value, Mapping):
        return None, ["permission_map_must_be_object"]
    normalized: dict[str, str] = {}
    reasons: list[str] = []
    for key, level in value.items():
        if not isinstance(key, str) or not key.strip():
            reasons.append("permission_scope_invalid")
            continue
        if level not in ALLOWED_PERMISSION_LEVELS:
            reasons.append(f"permission_level_invalid:{key}")
            continue
        normalized[key.strip()] = str(level)
    return dict(sorted(normalized.items())), reasons


def _normalize_job_permissions(
    value: object,
) -> tuple[dict[str, dict[str, str]] | None, list[str]]:
    if value is None:
        return None, []
    if not isinstance(value, Mapping):
        return None, ["job_permissions_must_be_object"]
    normalized: dict[str, dict[str, str]] = {}
    reasons: list[str] = []
    for job, permissions in value.items():
        if not isinstance(job, str) or not job.strip():
            reasons.append("job_name_invalid")
            continue
        mapping, mapping_reasons = _normalize_permissions(permissions)
        reasons.extend(f"job:{job}:{reason}" for reason in mapping_reasons)
        if mapping is not None:
            normalized[job.strip()] = mapping
    return dict(sorted(normalized.items())), reasons


def _requested_write_scopes(
    top_level: Mapping[str, str] | None,
    jobs: Mapping[str, Mapping[str, str]] | None,
) -> set[str]:
    scopes: set[str] = set()
    if top_level:
        scopes.update(f"{scope}: write" for scope, level in top_level.items() if level == "write")
    if jobs:
        for permissions in jobs.values():
            scopes.update(
                f"{scope}: write" for scope, level in permissions.items() if level == "write"
            )
    return scopes


def validate_workflow_permission_change_plan(
    repo_root: str | Path,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    current_index = build_workflow_permission_change_plan_index(repo_root)
    current_plans = current_index.get("plans", [])
    if not isinstance(current_plans, list):
        current_plans = []
    by_plan_id = {
        str(plan.get("plan_id", "")): plan for plan in current_plans if isinstance(plan, dict)
    }
    plan_id = candidate.get("plan_id")
    template = by_plan_id.get(str(plan_id)) if isinstance(plan_id, str) else None
    stale_reasons: list[str] = []
    invalid_reasons: list[str] = []

    if candidate.get("schema_version") != SCHEMA_VERSION:
        invalid_reasons.append("schema_version_mismatch")
    if template is None:
        stale_reasons.append("plan_not_current")
    else:
        immutable_fields = (
            "review_id",
            "workflow",
            "workflow_sha256",
            "permission_group",
            "decision_binding",
            "current_permission_snapshot",
            "proof_contract",
            "rollback_contract",
        )
        for field in immutable_fields:
            if candidate.get(field) != template.get(field):
                stale_reasons.append(f"binding_mismatch:{field}")
        if candidate.get("plan_digest") != template.get("plan_digest"):
            stale_reasons.append("plan_digest_mismatch")

    implementation = candidate.get("implementation")
    if not isinstance(implementation, dict):
        invalid_reasons.append("implementation_missing")
        implementation = {}
    if implementation.get("implementation_scope") != "permissions_only":
        invalid_reasons.append("implementation_scope_invalid")

    top_level, top_reasons = _normalize_permissions(implementation.get("top_level_permissions"))
    jobs, job_reasons = _normalize_job_permissions(implementation.get("job_permissions"))
    invalid_reasons.extend(top_reasons)
    invalid_reasons.extend(job_reasons)
    if top_level is None and jobs is None:
        invalid_reasons.append("target_permissions_missing")
    if (
        not isinstance(implementation.get("implementation_rationale"), str)
        or not str(implementation.get("implementation_rationale", "")).strip()
    ):
        invalid_reasons.append("implementation_rationale_missing")

    existing_writes: set[str] = set()
    if template is not None:
        snapshot = template.get("current_permission_snapshot", {})
        if isinstance(snapshot, dict):
            existing_writes = {
                str(scope)
                for scope in snapshot.get("granted_write_scopes", [])
                if isinstance(scope, str)
            }
    requested_writes = _requested_write_scopes(top_level, jobs)
    new_writes = sorted(requested_writes - existing_writes)
    if new_writes:
        invalid_reasons.extend(f"new_write_scope_forbidden:{scope}" for scope in new_writes)

    proof_refs = implementation.get("proof_execution_refs")
    if not isinstance(proof_refs, list):
        invalid_reasons.append("proof_execution_refs_must_be_list")
    rollback_ref = implementation.get("rollback_execution_ref")
    if rollback_ref is not None and (not isinstance(rollback_ref, str) or not rollback_ref.strip()):
        invalid_reasons.append("rollback_execution_ref_invalid")

    if candidate.get("ready_for_patch") is not False:
        invalid_reasons.append("ready_for_patch_must_remain_false")
    if candidate.get("safe_to_patch") is not False:
        invalid_reasons.append("safe_to_patch_must_remain_false")
    if candidate.get("requires_separate_reviewed_pr") is not True:
        invalid_reasons.append("separate_reviewed_pr_boundary_missing")
    if candidate.get("authority_boundary") != authority_boundary():
        invalid_reasons.append("authority_boundary_mismatch")

    stale_reasons = sorted(set(stale_reasons))
    invalid_reasons = sorted(set(invalid_reasons))
    if invalid_reasons:
        status = "invalid"
    elif stale_reasons:
        status = "stale"
    else:
        status = "structurally_ready_for_separate_pr"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "valid_current": status == "structurally_ready_for_separate_pr",
        "stale": status == "stale",
        "plan_id": plan_id,
        "stale_reasons": stale_reasons,
        "invalid_reasons": invalid_reasons,
        "requested_write_scopes": sorted(requested_writes),
        "existing_write_scopes": sorted(existing_writes),
        "new_write_scopes": new_writes,
        "implementation_authorized": False,
        "safe_to_patch": False,
        "authority_boundary": authority_boundary(),
    }


def validate_workflow_permission_change_plan_index(
    repo_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = build_workflow_permission_change_plan_index(repo_root)
    reasons: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        reasons.append("schema_version_mismatch")
    if payload.get("input_provenance", {}).get("input_digest") != current.get(
        "input_provenance", {}
    ).get("input_digest"):
        reasons.append("input_digest_mismatch")
    if payload.get("bundle_digest") != current.get("bundle_digest"):
        reasons.append("bundle_digest_mismatch")
    if payload.get("summary") != current.get("summary"):
        reasons.append("summary_mismatch")
    if payload.get("plan_index") != current.get("plan_index"):
        reasons.append("plan_index_mismatch")
    if payload.get("plans") != current.get("plans"):
        reasons.append("plans_mismatch")
    if payload.get("authority_boundary") != authority_boundary():
        reasons.append("authority_boundary_mismatch")
    reasons = sorted(set(reasons))
    return {
        "status": "fresh" if not reasons else "stale",
        "fresh": not reasons,
        "reasons": reasons,
        "current_input_digest": current.get("input_provenance", {}).get("input_digest", ""),
        "recorded_input_digest": payload.get("input_provenance", {}).get("input_digest", ""),
        "authority_boundary": authority_boundary(),
    }


def render_index_text(index: dict[str, Any]) -> str:
    summary = index.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return "\n".join(
        [
            f"status={index.get('status', 'unknown')}",
            f"change_plan_count={summary.get('change_plan_count', 0)}",
            f"reduce_or_split_decision_count={summary.get('reduce_or_split_decision_count', 0)}",
            f"non_change_decision_count={summary.get('non_change_decision_count', 0)}",
            f"pending_human_review_count={summary.get('pending_human_review_count', 0)}",
            f"bundle_digest={index.get('bundle_digest', '')}",
            "automatic_patch_generation_allowed=false",
            "implementation_authorized=false",
            "permission_mutation_allowed=false",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.workflow_permission_change_plan",
        description="Generate non-executable permission-only change-plan templates from current human decisions.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    index = build_workflow_permission_change_plan_index(ns.root)
    if ns.out:
        root = Path(ns.root).resolve()
        out = Path(ns.out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if ns.format == "json":
        sys.stdout.write(json.dumps(index, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_index_text(index) + "\n")
    return 1 if index.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
