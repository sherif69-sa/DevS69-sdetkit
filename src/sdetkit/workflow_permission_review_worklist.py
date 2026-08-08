from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .workflow_permission_governance_state_machine import (
    build_workflow_permission_governance_state_machine,
)
from .workflow_permission_review_packet import build_workflow_permission_review_packet_index

SCHEMA_VERSION = "sdetkit.workflow_permission_review_worklist.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-review-worklist.v1.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_review_worklist.py"
DIGEST_ALGORITHM = "sha256"

REVIEW_ACTIONS = (
    "complete_human_permission_review",
    "revisit_deferred_permission_review",
)
IMPLEMENTATION_ACTIONS = ("complete_permission_change_plan",)
REPAIR_ACTION = "repair_governance_evidence_binding"
ACTION_ORDER = (
    REPAIR_ACTION,
    "complete_human_permission_review",
    "revisit_deferred_permission_review",
    "complete_permission_change_plan",
)

AUTHORITY_FIELDS = (
    "automation_allowed",
    "commit_allowed",
    "human_decision_fabrication_allowed",
    "implementation_authorized",
    "merge_authorized",
    "patch_application_allowed",
    "permission_mutation_allowed",
    "review_assignment_allowed",
    "review_priority_inference_allowed",
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


def _dict_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _index_by_review_id(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        review_id = item.get("review_id")
        if isinstance(review_id, str) and review_id:
            indexed.setdefault(review_id, []).append(item)
    return indexed


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _packet_binding_reasons(
    lifecycle: dict[str, Any],
    packets: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    if len(packets) != 1:
        return None, ["packet_missing" if not packets else "duplicate_packets"]

    packet = packets[0]
    reasons: list[str] = []
    for field in ("review_id", "workflow", "workflow_sha256", "permission_group"):
        if lifecycle.get(field) != packet.get(field):
            reasons.append(f"packet_binding_mismatch:{field}")
    if lifecycle.get("packet_digest") != packet.get("packet_digest"):
        reasons.append("packet_digest_mismatch")
    if packet.get("safe_to_patch") is not False:
        reasons.append("packet_safe_to_patch_not_false")
    boundary = packet.get("authority_boundary")
    if not isinstance(boundary, dict) or not boundary or any(boundary.values()):
        reasons.append("packet_authority_boundary_invalid")
    return packet, sorted(set(reasons))


def _build_work_item(
    lifecycle: dict[str, Any],
    packets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    next_action = str(lifecycle.get("next_human_action", "none"))
    if next_action == "none":
        return None

    packet, packet_reasons = _packet_binding_reasons(lifecycle, packets)
    integrity_reasons = _string_list(lifecycle.get("integrity_reasons"))
    reasons = sorted(set([*integrity_reasons, *packet_reasons]))
    lifecycle_state = str(lifecycle.get("lifecycle_state", "blocked"))
    effective_action = next_action
    if lifecycle_state == "blocked" or reasons:
        effective_action = REPAIR_ACTION

    current_permissions: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    decision_boundary: dict[str, Any] = {}
    triage_signals: dict[str, Any] = {}
    packet_id: object = None
    packet_digest: object = lifecycle.get("packet_digest")
    if packet is not None:
        packet_id = packet.get("packet_id")
        packet_digest = packet.get("packet_digest")
        raw_permissions = packet.get("current_permissions")
        raw_evidence = packet.get("evidence")
        raw_boundary = packet.get("decision_boundary")
        raw_triage = packet.get("triage_signals")
        if isinstance(raw_permissions, dict):
            current_permissions = raw_permissions
        if isinstance(raw_evidence, dict):
            evidence = raw_evidence
        if isinstance(raw_boundary, dict):
            decision_boundary = raw_boundary
        if isinstance(raw_triage, dict):
            triage_signals = raw_triage

    review_id = str(lifecycle.get("review_id", ""))
    is_review_action = effective_action in REVIEW_ACTIONS
    return {
        "work_item_id": f"work-{review_id or 'unknown'}",
        "review_id": review_id,
        "workflow": lifecycle.get("workflow"),
        "workflow_sha256": lifecycle.get("workflow_sha256"),
        "permission_group": lifecycle.get("permission_group"),
        "lifecycle_state": lifecycle_state,
        "next_human_action": effective_action,
        "packet_id": packet_id,
        "packet_digest": packet_digest,
        "packet_json_name": f"{review_id}.json" if review_id else None,
        "packet_markdown_name": f"{review_id}.md" if review_id else None,
        "current_write_scopes": _string_list(current_permissions.get("write_scopes")),
        "triage_signals": dict(sorted(triage_signals.items())),
        "required_human_evidence": _string_list(evidence.get("required_human_evidence")),
        "retained_evidence_refs": _string_list(evidence.get("retained_evidence_refs")),
        "allowed_human_decisions": _string_list(decision_boundary.get("allowed_decisions"))
        if is_review_action
        else [],
        "current_human_decision": lifecycle.get("human_decision"),
        "decision_record_ref": lifecycle.get("decision_record_ref"),
        "plan_id": lifecycle.get("plan_id"),
        "plan_digest": lifecycle.get("plan_digest"),
        "integrity_reasons": reasons,
        "machine_recommendation": None,
        "review_priority": None,
        "reviewer_assignment": None,
        "decision_prefill": None,
        "safe_to_patch": False,
        "authority_boundary": authority_boundary(),
    }


def workflow_permission_review_worklist_input_provenance(
    repo_root: str | Path = ".",
    *,
    state_machine: dict[str, Any] | None = None,
    packet_index: dict[str, Any] | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    state = state_machine or build_workflow_permission_governance_state_machine(root)
    packets = packet_index or build_workflow_permission_review_packet_index(root)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )

    state_provenance = state.get("input_provenance")
    packet_provenance = packets.get("input_provenance")
    if not isinstance(state_provenance, dict):
        state_provenance = {}
    if not isinstance(packet_provenance, dict):
        packet_provenance = {}

    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator.read_bytes()),
        (
            "state_machine_input_digest",
            str(state_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        ("state_machine_bundle_digest", str(state.get("bundle_digest", "")).encode("utf-8")),
        (
            "review_packet_input_digest",
            str(packet_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        ("review_packet_bundle_digest", str(packets.get("bundle_digest", "")).encode("utf-8")),
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
        "state_machine_input_digest": state_provenance.get("input_digest", ""),
        "state_machine_bundle_digest": state.get("bundle_digest", ""),
        "review_packet_input_digest": packet_provenance.get("input_digest", ""),
        "review_packet_bundle_digest": packets.get("bundle_digest", ""),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "contract_path": CONTRACT_PATH,
    }


def _build_action_lanes(work_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lanes: list[dict[str, Any]] = []
    for action in ACTION_ORDER:
        lane_items = [item for item in work_items if item.get("next_human_action") == action]
        if not lane_items:
            continue
        group_counts: dict[str, int] = {}
        for item in lane_items:
            group = str(item.get("permission_group", "unknown"))
            group_counts[group] = group_counts.get(group, 0) + 1
        lanes.append(
            {
                "next_human_action": action,
                "work_item_count": len(lane_items),
                "permission_group_counts": dict(sorted(group_counts.items())),
                "work_item_ids": [str(item.get("work_item_id", "")) for item in lane_items],
            }
        )
    return lanes


def build_workflow_permission_review_worklist(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    state = build_workflow_permission_governance_state_machine(root)
    packet_index = build_workflow_permission_review_packet_index(root)

    lifecycle = _dict_items(state.get("lifecycle"))
    packets = _dict_items(packet_index.get("packets"))
    packets_by_id = _index_by_review_id(packets)

    work_items: list[dict[str, Any]] = []
    resolved_no_action_count = 0
    for lifecycle_item in lifecycle:
        review_id = str(lifecycle_item.get("review_id", ""))
        work_item = _build_work_item(lifecycle_item, packets_by_id.get(review_id, []))
        if work_item is None:
            resolved_no_action_count += 1
            continue
        work_items.append(work_item)

    work_items.sort(key=lambda item: str(item.get("workflow", "")))
    action_lanes = _build_action_lanes(work_items)
    blocked_count = sum(item.get("next_human_action") == REPAIR_ACTION for item in work_items)
    review_count = sum(item.get("next_human_action") in REVIEW_ACTIONS for item in work_items)
    implementation_count = sum(
        item.get("next_human_action") in IMPLEMENTATION_ACTIONS for item in work_items
    )
    group_counts: dict[str, int] = {}
    for item in work_items:
        group = str(item.get("permission_group", "unknown"))
        group_counts[group] = group_counts.get(group, 0) + 1

    state_integrity = state.get("integrity")
    if not isinstance(state_integrity, dict):
        state_integrity = {}
    global_reasons = _string_list(state_integrity.get("global_reasons"))
    if state.get("status") == "blocked" and not global_reasons:
        global_reasons.append("upstream_state_machine_blocked")
    if state.get("status") not in {"blocked", "not_required", "human_action_required", "complete"}:
        global_reasons.append("upstream_state_machine_status_invalid")
    global_reasons = sorted(set(global_reasons))

    if global_reasons or blocked_count:
        status = "blocked"
    elif work_items:
        status = "human_work_required"
    else:
        status = "not_required"

    digest_items = [
        {
            "work_item_id": item["work_item_id"],
            "review_id": item["review_id"],
            "workflow": item["workflow"],
            "workflow_sha256": item["workflow_sha256"],
            "permission_group": item["permission_group"],
            "lifecycle_state": item["lifecycle_state"],
            "next_human_action": item["next_human_action"],
            "packet_digest": item["packet_digest"],
            "plan_digest": item["plan_digest"],
            "integrity_reasons": item["integrity_reasons"],
        }
        for item in work_items
    ]
    bundle_digest = _sha256_bytes(
        _canonical_json_bytes(
            {
                "action_lanes": action_lanes,
                "global_reasons": global_reasons,
                "work_items": digest_items,
            }
        )
    )
    provenance = workflow_permission_review_worklist_input_provenance(
        root,
        state_machine=state,
        packet_index=packet_index,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "input_provenance": provenance,
        "summary": {
            "workflow_count": len(lifecycle),
            "work_item_count": len(work_items),
            "review_action_count": review_count,
            "implementation_action_count": implementation_count,
            "blocked_repair_count": blocked_count,
            "resolved_no_action_count": resolved_no_action_count,
            "permission_group_counts": dict(sorted(group_counts.items())),
            "machine_recommendation_count": 0,
            "machine_priority_count": 0,
            "automatic_reviewer_assignment_count": 0,
            "automatic_decision_count": 0,
            "automatic_permission_change_count": 0,
        },
        "global_reasons": global_reasons,
        "action_lanes": action_lanes,
        "bundle_digest": bundle_digest,
        "work_items": work_items,
        "rules": {
            "exact_stage7_lifecycle_required": True,
            "exact_review_packet_binding_required": True,
            "blocked_items_are_repair_only": True,
            "machine_recommendation_allowed": False,
            "machine_priority_allowed": False,
            "automatic_reviewer_assignment_allowed": False,
            "automatic_decision_allowed": False,
            "implementation_remains_separate_reviewed_pr": True,
            "workflow_mutation_allowed": False,
        },
        "authority_boundary": authority_boundary(),
    }


def validate_workflow_permission_review_worklist(
    repo_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = build_workflow_permission_review_worklist(repo_root)
    reasons: list[str] = []
    for field in (
        "schema_version",
        "summary",
        "global_reasons",
        "action_lanes",
        "bundle_digest",
        "work_items",
    ):
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
        raise ValueError("repository-local review worklist output may only be written under build/")
    return target


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("review worklist must be a JSON object")
    return payload


def render_worklist_text(payload: dict[str, Any]) -> str:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    lines = [
        "Workflow Permission Review Worklist v1",
        f"status={payload.get('status', 'unknown')}",
        f"workflow_count={summary.get('workflow_count', 0)}",
        f"work_item_count={summary.get('work_item_count', 0)}",
        f"review_action_count={summary.get('review_action_count', 0)}",
        f"implementation_action_count={summary.get('implementation_action_count', 0)}",
        f"blocked_repair_count={summary.get('blocked_repair_count', 0)}",
        f"bundle_digest={payload.get('bundle_digest', '')}",
        "machine_recommendation_allowed=false",
        "machine_priority_allowed=false",
        "permission_mutation_allowed=false",
        "merge_authorized=false",
    ]
    for item in _dict_items(payload.get("work_items")):
        lines.append(
            f"{item.get('workflow', 'unknown')}: {item.get('next_human_action', 'unknown')} "
            f"[{item.get('permission_group', 'unknown')}]"
        )
    return "\n".join(lines) + "\n"


def render_validation_text(payload: dict[str, Any]) -> str:
    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    lines = [
        "Workflow Permission Review Worklist Validation v1",
        f"status={payload.get('status', 'unknown')}",
        f"fresh={str(payload.get('fresh') is True).lower()}",
        f"reason_count={len(reasons)}",
        f"current_bundle_digest={payload.get('current_bundle_digest', '')}",
        "machine_recommendation_allowed=false",
        "permission_mutation_allowed=false",
        "merge_authorized=false",
    ]
    lines.extend(f"reason={reason}" for reason in reasons)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic human workflow-permission review worklist"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--check-index")
    parser.add_argument("--fail-on-stale", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.check_index:
        result = validate_workflow_permission_review_worklist(
            root,
            _load_json(_safe_output_path(root, Path(args.check_index))),
        )
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(render_validation_text(result), end="")
        return 1 if args.fail_on_stale and not result["fresh"] else 0

    payload = build_workflow_permission_review_worklist(root)
    if args.out:
        output = _safe_output_path(root, Path(args.out))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_worklist_text(payload), end="")
    return 1 if payload.get("status") == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
