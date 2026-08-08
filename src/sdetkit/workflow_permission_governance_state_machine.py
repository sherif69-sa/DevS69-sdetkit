from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .workflow_permission_change_plan import build_workflow_permission_change_plan_index
from .workflow_permission_review_control_plane import build_workflow_permission_review_control_plane
from .workflow_permission_review_packet import build_workflow_permission_review_packet_index

SCHEMA_VERSION = "sdetkit.workflow_permission_governance_state_machine.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-governance-state-machine.v1.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_governance_state_machine.py"
DIGEST_ALGORITHM = "sha256"
PLAN_DECISIONS = ("reduce", "split")

AUTHORITY_FIELDS = (
    "automation_allowed",
    "commit_allowed",
    "human_decision_fabrication_allowed",
    "implementation_authorized",
    "merge_authorized",
    "patch_application_allowed",
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


def _zero_authority(value: object) -> bool:
    return isinstance(value, dict) and bool(value) and all(flag is False for flag in value.values())


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _index_by_review_id(
    items: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    missing_ids: list[str] = []
    for item in items:
        review_id = item.get("review_id")
        if not isinstance(review_id, str) or not review_id:
            missing_ids.append(str(item.get("workflow", "unknown")))
            continue
        indexed.setdefault(review_id, []).append(item)
    return indexed, sorted(set(missing_ids))


def _packet_binding_reasons(control: dict[str, Any], packet: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field in ("review_id", "workflow", "workflow_sha256", "permission_group"):
        if control.get(field) != packet.get(field):
            reasons.append(f"packet_binding_mismatch:{field}")

    boundary = packet.get("decision_boundary")
    if not isinstance(boundary, dict):
        reasons.append("packet_decision_boundary_missing")
    else:
        if boundary.get("human_decision_recorded") != control.get("human_decision_recorded"):
            reasons.append("packet_decision_state_mismatch")
        if control.get("human_decision_recorded") is True:
            if boundary.get("current_human_decision") != control.get("human_decision"):
                reasons.append("packet_human_decision_mismatch")
            if boundary.get("decision_record_ref") != control.get("decision_record_ref"):
                reasons.append("packet_decision_record_ref_mismatch")

    if packet.get("safe_to_patch") is not False:
        reasons.append("packet_safe_to_patch_not_false")
    if not _zero_authority(packet.get("authority_boundary")):
        reasons.append("packet_authority_boundary_invalid")
    return reasons


def _plan_binding_reasons(control: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field in ("review_id", "workflow", "workflow_sha256", "permission_group"):
        if control.get(field) != plan.get(field):
            reasons.append(f"plan_binding_mismatch:{field}")

    binding = plan.get("decision_binding")
    if not isinstance(binding, dict):
        reasons.append("plan_decision_binding_missing")
    else:
        if binding.get("decision") != control.get("human_decision"):
            reasons.append("plan_binding_mismatch:decision")
        if binding.get("decision_record_ref") != control.get("decision_record_ref"):
            reasons.append("plan_binding_mismatch:decision_record_ref")

    if plan.get("ready_for_patch") is not False:
        reasons.append("plan_ready_for_patch_not_false")
    if plan.get("safe_to_patch") is not False:
        reasons.append("plan_safe_to_patch_not_false")
    if not _zero_authority(plan.get("authority_boundary")):
        reasons.append("plan_authority_boundary_invalid")
    return reasons


def _build_lifecycle_item(
    control: dict[str, Any],
    packets: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    missing_record_bindings: set[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    workflow = str(control.get("workflow", "unknown"))
    review_id = str(control.get("review_id", ""))

    if not _zero_authority(control.get("authority_boundary")):
        reasons.append("control_plane_authority_boundary_invalid")
    if control.get("safe_to_patch") is not False:
        reasons.append("control_plane_safe_to_patch_not_false")

    packet: dict[str, Any] | None = None
    if len(packets) != 1:
        reasons.append("packet_missing" if not packets else "duplicate_packets")
    else:
        packet = packets[0]
        reasons.extend(_packet_binding_reasons(control, packet))

    if len(plans) > 1:
        reasons.append("duplicate_change_plans")

    decision_recorded = control.get("human_decision_recorded") is True
    decision = control.get("human_decision")
    lifecycle_state = "pending_human_review"
    next_human_action = "complete_human_permission_review"

    if not decision_recorded:
        if plans:
            reasons.append("change_plan_without_human_decision")
    elif decision == "keep":
        lifecycle_state = "resolved_keep"
        next_human_action = "none"
        if plans:
            reasons.append("change_plan_for_keep_decision")
    elif decision == "defer":
        lifecycle_state = "deferred"
        next_human_action = "revisit_deferred_permission_review"
        if plans:
            reasons.append("change_plan_for_defer_decision")
    elif decision in PLAN_DECISIONS:
        lifecycle_state = "implementation_plan_required"
        next_human_action = "complete_permission_change_plan"
        if workflow in missing_record_bindings:
            reasons.append("missing_decision_record_binding")
        if len(plans) != 1:
            reasons.append("change_plan_missing" if not plans else "duplicate_change_plans")
        else:
            reasons.extend(_plan_binding_reasons(control, plans[0]))
    else:
        reasons.append("human_decision_invalid")

    reasons = sorted(set(reasons))
    if reasons:
        lifecycle_state = "blocked"
        next_human_action = "repair_governance_evidence_binding"

    return {
        "review_id": review_id,
        "workflow": workflow,
        "workflow_sha256": control.get("workflow_sha256"),
        "permission_group": control.get("permission_group"),
        "human_decision_recorded": decision_recorded,
        "human_decision": decision if decision_recorded else None,
        "decision_record_ref": control.get("decision_record_ref"),
        "packet_digest": packet.get("packet_digest") if packet is not None else None,
        "plan_id": plans[0].get("plan_id") if len(plans) == 1 else None,
        "plan_digest": plans[0].get("plan_digest") if len(plans) == 1 else None,
        "lifecycle_state": lifecycle_state,
        "next_human_action": next_human_action,
        "integrity_reasons": reasons,
        "safe_to_patch": False,
        "authority_boundary": authority_boundary(),
    }


def workflow_permission_governance_state_input_provenance(
    repo_root: str | Path = ".",
    *,
    control_plane: dict[str, Any] | None = None,
    packet_index: dict[str, Any] | None = None,
    change_plan_index: dict[str, Any] | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    control = control_plane or build_workflow_permission_review_control_plane(root)
    packets = packet_index or build_workflow_permission_review_packet_index(root)
    changes = change_plan_index or build_workflow_permission_change_plan_index(root)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )

    control_provenance = control.get("input_provenance")
    packet_provenance = packets.get("input_provenance")
    change_provenance = changes.get("input_provenance")
    if not isinstance(control_provenance, dict):
        control_provenance = {}
    if not isinstance(packet_provenance, dict):
        packet_provenance = {}
    if not isinstance(change_provenance, dict):
        change_provenance = {}

    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator.read_bytes()),
        (
            "control_plane_input_digest",
            str(control_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        (
            "packet_input_digest",
            str(packet_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        ("packet_bundle_digest", str(packets.get("bundle_digest", "")).encode("utf-8")),
        (
            "change_plan_input_digest",
            str(change_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        ("change_plan_bundle_digest", str(changes.get("bundle_digest", "")).encode("utf-8")),
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
        "control_plane_input_digest": control_provenance.get("input_digest", ""),
        "packet_input_digest": packet_provenance.get("input_digest", ""),
        "packet_bundle_digest": packets.get("bundle_digest", ""),
        "change_plan_input_digest": change_provenance.get("input_digest", ""),
        "change_plan_bundle_digest": changes.get("bundle_digest", ""),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "contract_path": CONTRACT_PATH,
    }


def build_workflow_permission_governance_state_machine(
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    control = build_workflow_permission_review_control_plane(root)
    packet_index = build_workflow_permission_review_packet_index(root)
    change_index = build_workflow_permission_change_plan_index(root)

    control_items = _dict_items(control.get("review_queue"))
    packet_items = _dict_items(packet_index.get("packets"))
    plan_items = _dict_items(change_index.get("plans"))
    packets_by_id, packet_missing_ids = _index_by_review_id(packet_items)
    plans_by_id, plan_missing_ids = _index_by_review_id(plan_items)

    known_ids = {
        str(item.get("review_id"))
        for item in control_items
        if isinstance(item.get("review_id"), str) and item.get("review_id")
    }
    orphan_packets = sorted(review_id for review_id in packets_by_id if review_id not in known_ids)
    orphan_plans = sorted(review_id for review_id in plans_by_id if review_id not in known_ids)
    missing_record_bindings = {
        workflow
        for workflow in change_index.get("missing_decision_record_bindings", [])
        if isinstance(workflow, str)
    }

    lifecycle = [
        _build_lifecycle_item(
            item,
            packets_by_id.get(str(item.get("review_id", "")), []),
            plans_by_id.get(str(item.get("review_id", "")), []),
            missing_record_bindings,
        )
        for item in control_items
    ]
    lifecycle.sort(key=lambda item: str(item.get("workflow", "")))

    global_reasons: list[str] = []
    if packet_missing_ids:
        global_reasons.append("packet_without_review_id")
    if plan_missing_ids:
        global_reasons.append("plan_without_review_id")
    if orphan_packets:
        global_reasons.append("orphan_packets")
    if orphan_plans:
        global_reasons.append("orphan_change_plans")
    for label, payload in (
        ("control_plane", control),
        ("review_packet", packet_index),
        ("change_plan", change_index),
    ):
        if not _zero_authority(payload.get("authority_boundary")):
            global_reasons.append(f"{label}_authority_boundary_invalid")
    global_reasons = sorted(set(global_reasons))

    blocked_count = sum(item["lifecycle_state"] == "blocked" for item in lifecycle)
    action_count = sum(item["next_human_action"] != "none" for item in lifecycle)
    if global_reasons or blocked_count:
        status = "blocked"
    elif not lifecycle:
        status = "not_required"
    elif action_count:
        status = "human_action_required"
    else:
        status = "complete"

    state_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    for item in lifecycle:
        lifecycle_state = str(item["lifecycle_state"])
        action = str(item["next_human_action"])
        state_counts[lifecycle_state] = state_counts.get(lifecycle_state, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1

    integrity = {
        "global_reasons": global_reasons,
        "orphan_packet_review_ids": orphan_packets,
        "orphan_plan_review_ids": orphan_plans,
        "packet_without_review_id_workflows": packet_missing_ids,
        "plan_without_review_id_workflows": plan_missing_ids,
    }
    digest_refs = [
        {
            "review_id": item["review_id"],
            "workflow": item["workflow"],
            "workflow_sha256": item["workflow_sha256"],
            "lifecycle_state": item["lifecycle_state"],
            "next_human_action": item["next_human_action"],
            "packet_digest": item["packet_digest"],
            "plan_digest": item["plan_digest"],
            "integrity_reasons": item["integrity_reasons"],
        }
        for item in lifecycle
    ]
    bundle_digest = _sha256_bytes(
        _canonical_json_bytes({"integrity": integrity, "lifecycle": digest_refs})
    )
    provenance = workflow_permission_governance_state_input_provenance(
        root,
        control_plane=control,
        packet_index=packet_index,
        change_plan_index=change_index,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "input_provenance": provenance,
        "summary": {
            "workflow_count": len(lifecycle),
            "blocked_count": blocked_count,
            "human_action_required_count": action_count,
            "state_counts": dict(sorted(state_counts.items())),
            "next_human_action_counts": dict(sorted(action_counts.items())),
            "orphan_packet_count": len(orphan_packets),
            "orphan_change_plan_count": len(orphan_plans),
            "automatic_decision_allowed": False,
            "automatic_permission_change_allowed": False,
        },
        "integrity": integrity,
        "bundle_digest": bundle_digest,
        "lifecycle": lifecycle,
        "rules": {
            "one_packet_per_review_item_required": True,
            "one_change_plan_per_reduce_or_split_decision_required": True,
            "pending_review_may_not_have_change_plan": True,
            "keep_or_defer_may_not_have_change_plan": True,
            "exact_workflow_digest_binding_required": True,
            "exact_decision_record_binding_required": True,
            "one_next_human_action_per_workflow": True,
            "reporting_only": True,
        },
        "authority_boundary": authority_boundary(),
    }


def validate_workflow_permission_governance_state_machine(
    repo_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = build_workflow_permission_governance_state_machine(repo_root)
    reasons: list[str] = []
    for field in ("schema_version", "summary", "integrity", "bundle_digest", "lifecycle"):
        if payload.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    recorded_provenance = payload.get("input_provenance")
    current_provenance = current.get("input_provenance")
    if not isinstance(recorded_provenance, dict):
        recorded_provenance = {}
    if not isinstance(current_provenance, dict):
        current_provenance = {}
    if recorded_provenance.get("input_digest") != current_provenance.get("input_digest"):
        reasons.append("input_digest_mismatch")
    if payload.get("authority_boundary") != authority_boundary():
        reasons.append("authority_boundary_mismatch")

    reasons = sorted(set(reasons))
    return {
        "status": "fresh" if not reasons else "stale",
        "fresh": not reasons,
        "reasons": reasons,
        "recorded_input_digest": recorded_provenance.get("input_digest", ""),
        "current_input_digest": current_provenance.get("input_digest", ""),
        "recorded_bundle_digest": payload.get("bundle_digest", ""),
        "current_bundle_digest": current.get("bundle_digest", ""),
        "authority_boundary": authority_boundary(),
    }


def _safe_output_path(root: Path, output: Path) -> Path:
    target = output.resolve() if output.is_absolute() else (root / output).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        return target
    if not relative.parts or relative.parts[0] != "build":
        raise ValueError(
            "repository-local governance state output may only be written under build/"
        )
    return target


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("governance state index must be a JSON object")
    return payload


def render_state_text(payload: dict[str, Any]) -> str:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    lines = [
        "Workflow Permission Governance State Machine v1",
        f"status={payload.get('status', 'unknown')}",
        f"workflow_count={summary.get('workflow_count', 0)}",
        f"blocked_count={summary.get('blocked_count', 0)}",
        f"human_action_required_count={summary.get('human_action_required_count', 0)}",
        f"bundle_digest={payload.get('bundle_digest', '')}",
        "permission_mutation_allowed=false",
        "implementation_authorized=false",
        "merge_authorized=false",
    ]
    for item in _dict_items(payload.get("lifecycle")):
        lines.append(
            f"{item.get('workflow', 'unknown')}: {item.get('lifecycle_state', 'unknown')} -> "
            f"{item.get('next_human_action', 'unknown')}"
        )
    return "\n".join(lines) + "\n"


def render_validation_text(payload: dict[str, Any]) -> str:
    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    lines = [
        "Workflow Permission Governance State Validation v1",
        f"status={payload.get('status', 'unknown')}",
        f"fresh={str(payload.get('fresh') is True).lower()}",
        f"reason_count={len(reasons)}",
        f"current_bundle_digest={payload.get('current_bundle_digest', '')}",
        "permission_mutation_allowed=false",
        "merge_authorized=false",
    ]
    lines.extend(f"reason={reason}" for reason in reasons)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report workflow permission governance lifecycle integrity"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--check-index")
    parser.add_argument("--fail-on-stale", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.check_index:
        result = validate_workflow_permission_governance_state_machine(
            root,
            _load_json(_safe_output_path(root, Path(args.check_index))),
        )
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(render_validation_text(result), end="")
        return 1 if args.fail_on_stale and not result["fresh"] else 0

    payload = build_workflow_permission_governance_state_machine(root)
    if args.out:
        output = _safe_output_path(root, Path(args.out))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_state_text(payload), end="")
    return 1 if payload.get("status") == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
