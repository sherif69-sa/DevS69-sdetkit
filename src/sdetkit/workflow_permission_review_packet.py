from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .workflow_permission_decision_record import authority_boundary as decision_authority_boundary
from .workflow_permission_review_control_plane import build_workflow_permission_review_control_plane

SCHEMA_VERSION = "sdetkit.workflow_permission_review_packet.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-review-packet.v1.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_review_packet.py"
REVIEW_CARD_DIR = "docs/ci/workflow-permission-review-cards"
DEFAULT_INDEX_NAME = "workflow-permission-review-packet-index.json"
DEFAULT_MARKDOWN_INDEX_NAME = "workflow-permission-review-packet-index.md"
DIGEST_ALGORITHM = "sha256"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "human_decision_fabrication_allowed",
    "implementation_authorized",
    "merge_authorized",
    "patch_application_allowed",
    "permission_mutation_allowed",
    "security_dismissal_allowed",
    "semantic_equivalence_proven",
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


def _review_card_refs(root: Path, workflow: str, permission_group: str) -> list[str]:
    directory = root / REVIEW_CARD_DIR
    if not directory.is_dir():
        return []

    refs: list[str] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if workflow in text or permission_group in text:
            refs.append(path.relative_to(root).as_posix())
    return refs


def _triage_signals(write_scopes: Sequence[str]) -> dict[str, Any]:
    scopes = sorted(set(write_scopes))
    return {
        "write_scope_count": len(scopes),
        "contains_contents_write": "contents: write" in scopes,
        "contains_id_token_write": "id-token: write" in scopes,
        "contains_issues_write": "issues: write" in scopes,
        "contains_packages_write": "packages: write" in scopes,
        "contains_pages_write": "pages: write" in scopes,
        "contains_pull_requests_write": "pull-requests: write" in scopes,
        "contains_security_events_write": "security-events: write" in scopes,
        "multiple_write_scopes": len(scopes) > 1,
        "classification_is_decision": False,
        "classification_authorizes_change": False,
    }


def _decision_template(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "template_only": True,
        "human_completion_required": True,
        "schema_version": "sdetkit.workflow_permission_decision_record.v1",
        "review_id": entry.get("review_id"),
        "workflow": entry.get("workflow"),
        "workflow_sha256": entry.get("workflow_sha256"),
        "permission_group": entry.get("permission_group"),
        "decision": None,
        "reviewer": None,
        "reviewer_evidence": None,
        "decided_at": None,
        "rationale": None,
        "proposed_change": None,
        "proof_contract": list(entry.get("proof_contract", [])),
        "rollback_contract": entry.get("rollback_contract"),
        "authority_boundary": decision_authority_boundary(),
    }


def _packet_digest(packet: dict[str, Any]) -> str:
    digest_input = dict(packet)
    digest_input.pop("packet_digest", None)
    return _sha256_bytes(_canonical_json_bytes(digest_input))


def _build_packet(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    workflow = str(entry.get("workflow", ""))
    permission_group = str(entry.get("permission_group", "unknown"))
    write_scopes = [str(scope) for scope in entry.get("granted_write_scopes", [])]
    review_card_refs = _review_card_refs(root, workflow, permission_group)
    decision_evidence_refs = [str(ref) for ref in entry.get("decision_evidence_refs", [])]
    evidence_refs = sorted(set([*review_card_refs, *decision_evidence_refs]))
    human_decision_recorded = entry.get("human_decision_recorded") is True

    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": f"packet-{entry.get('review_id', 'unknown')}",
        "review_id": entry.get("review_id"),
        "workflow": workflow,
        "workflow_sha256": entry.get("workflow_sha256"),
        "permission_group": permission_group,
        "review_state": entry.get("review_state"),
        "current_permissions": {
            "write_scopes": sorted(set(write_scopes)),
            "scope_count": len(set(write_scopes)),
        },
        "evidence": {
            "inferred_permission_reasons": list(entry.get("inferred_permission_reasons", [])),
            "required_human_evidence": list(entry.get("required_human_evidence", [])),
            "review_card_refs": review_card_refs,
            "decision_evidence_refs": decision_evidence_refs,
            "retained_evidence_refs": evidence_refs,
            "retained_evidence_present": bool(evidence_refs),
            "generated_packet_is_human_evidence": False,
        },
        "triage_signals": _triage_signals(write_scopes),
        "decision_boundary": {
            "allowed_decisions": list(entry.get("allowed_decisions", [])),
            "human_decision_recorded": human_decision_recorded,
            "current_human_decision": entry.get("human_decision"),
            "decision_record_ref": entry.get("decision_record_ref"),
            "decision_record_refs": list(entry.get("decision_record_refs", [])),
            "machine_recommendation": None,
            "generated_packet_may_choose_decision": False,
            "decision_record_template": None
            if human_decision_recorded
            else _decision_template(entry),
        },
        "proof_contract": list(entry.get("proof_contract", [])),
        "rollback_contract": entry.get("rollback_contract"),
        "requires_human_review": entry.get("requires_human_review") is True,
        "safe_to_patch": False,
        "next_allowed_action": entry.get("next_allowed_action"),
        "authority_boundary": authority_boundary(),
    }
    packet["packet_digest"] = _packet_digest(packet)
    return packet


def workflow_permission_review_packet_input_provenance(
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


def build_workflow_permission_review_packet_index(
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    control_plane = build_workflow_permission_review_control_plane(root)
    queue = control_plane.get("review_queue", [])
    if not isinstance(queue, list):
        queue = []

    packets = [_build_packet(root, entry) for entry in queue if isinstance(entry, dict)]
    packets.sort(key=lambda item: str(item.get("workflow", "")))

    group_counts: dict[str, int] = {}
    pending_count = 0
    decided_count = 0
    retained_evidence_count = 0
    for packet in packets:
        group = str(packet.get("permission_group", "unknown"))
        group_counts[group] = group_counts.get(group, 0) + 1
        decision_boundary = packet.get("decision_boundary", {})
        if (
            isinstance(decision_boundary, dict)
            and decision_boundary.get("human_decision_recorded") is True
        ):
            decided_count += 1
        else:
            pending_count += 1
        evidence = packet.get("evidence", {})
        if isinstance(evidence, dict) and evidence.get("retained_evidence_present") is True:
            retained_evidence_count += 1

    packet_refs = [
        {
            "packet_id": packet["packet_id"],
            "review_id": packet["review_id"],
            "workflow": packet["workflow"],
            "workflow_sha256": packet["workflow_sha256"],
            "permission_group": packet["permission_group"],
            "review_state": packet["review_state"],
            "packet_digest": packet["packet_digest"],
            "json_path": f"{packet['review_id']}.json",
            "markdown_path": f"{packet['review_id']}.md",
        }
        for packet in packets
    ]
    bundle_digest = _sha256_bytes(_canonical_json_bytes({"packets": packet_refs}))
    provenance = workflow_permission_review_packet_input_provenance(
        root,
        control_plane=control_plane,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "not_required"
            if not packets
            else ("human_review_required" if pending_count else "human_decisions_recorded")
        ),
        "input_provenance": provenance,
        "summary": {
            "packet_count": len(packets),
            "permission_group_count": len(group_counts),
            "group_counts": dict(sorted(group_counts.items())),
            "pending_human_review_count": pending_count,
            "human_decision_recorded_count": decided_count,
            "retained_evidence_packet_count": retained_evidence_count,
            "machine_recommendation_count": 0,
            "decision_template_count": pending_count,
            "automatic_permission_change_allowed": False,
        },
        "bundle_digest": bundle_digest,
        "packet_index": packet_refs,
        "packets": packets,
        "rules": {
            "review_first": True,
            "packet_is_evidence_not_decision": True,
            "packet_may_not_prefill_decision": True,
            "packet_may_not_fabricate_reviewer": True,
            "exact_workflow_digest_required": True,
            "valid_decision_record_required_to_advance_state": True,
            "implementation_remains_separate_reviewed_pr": True,
            "workflow_mutation_allowed": False,
        },
        "authority_boundary": authority_boundary(),
    }


def validate_workflow_permission_review_packet_index(
    repo_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current = build_workflow_permission_review_packet_index(repo_root)
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
    if payload.get("packet_index") != current.get("packet_index"):
        reasons.append("packet_index_mismatch")
    if payload.get("authority_boundary") != authority_boundary():
        reasons.append("authority_boundary_mismatch")

    recorded_packets = payload.get("packets", [])
    current_packets = current.get("packets", [])
    if not isinstance(recorded_packets, list):
        recorded_packets = []
        reasons.append("packets_missing")
    if recorded_packets != current_packets:
        reasons.append("packets_mismatch")

    reasons = sorted(set(reasons))
    return {
        "status": "fresh" if not reasons else "stale",
        "fresh": not reasons,
        "reasons": reasons,
        "recorded_input_digest": payload.get("input_provenance", {}).get("input_digest", ""),
        "current_input_digest": current.get("input_provenance", {}).get("input_digest", ""),
        "recorded_bundle_digest": payload.get("bundle_digest", ""),
        "current_bundle_digest": current.get("bundle_digest", ""),
        "authority_boundary": authority_boundary(),
    }


def render_packet_markdown(packet: dict[str, Any]) -> str:
    permissions = packet.get("current_permissions", {})
    write_scopes = permissions.get("write_scopes", []) if isinstance(permissions, dict) else []
    evidence = packet.get("evidence", {})
    evidence_refs = evidence.get("retained_evidence_refs", []) if isinstance(evidence, dict) else []
    required_evidence = (
        evidence.get("required_human_evidence", []) if isinstance(evidence, dict) else []
    )
    decision_boundary = packet.get("decision_boundary", {})
    allowed_decisions = (
        decision_boundary.get("allowed_decisions", [])
        if isinstance(decision_boundary, dict)
        else []
    )

    lines = [
        f"# Workflow permission review packet: {packet.get('workflow', '')}",
        "",
        "> Generated evidence only. This packet is not a human decision and grants no permission-change, patch, merge, or workflow-mutation authority.",
        "",
        "## Exact binding",
        "",
        f"- Review ID: `{packet.get('review_id', '')}`",
        f"- Workflow: `{packet.get('workflow', '')}`",
        f"- Workflow SHA-256: `{packet.get('workflow_sha256', '')}`",
        f"- Permission group: `{packet.get('permission_group', '')}`",
        f"- Packet digest: `{packet.get('packet_digest', '')}`",
        "",
        "## Current write scopes",
        "",
    ]
    lines.extend([f"- `{scope}`" for scope in write_scopes] or ["- None detected."])
    lines.extend(["", "## Retained evidence references", ""])
    lines.extend(
        [f"- `{ref}`" for ref in evidence_refs] or ["- No retained card/decision evidence mapped."]
    )
    lines.extend(["", "## Human evidence still required", ""])
    lines.extend(
        [f"- {item}" for item in required_evidence]
        or ["- Follow the control-plane proof contract."]
    )
    lines.extend(["", "## Decision boundary", ""])
    lines.append("Allowed human decisions: " + ", ".join(f"`{item}`" for item in allowed_decisions))
    lines.extend(
        [
            "",
            "The generated packet does **not** choose or recommend a decision. A human reviewer must create a valid current decision record bound to these exact workflow bytes.",
            "",
            "## Proof contract",
            "",
        ]
    )
    lines.extend([f"- `{item}`" for item in packet.get("proof_contract", [])])
    lines.extend(["", "## Authority boundary", ""])
    lines.extend([f"- `{key}=false`" for key in sorted(authority_boundary())])
    lines.append("")
    return "\n".join(lines)


def render_index_markdown(index: dict[str, Any]) -> str:
    summary = index.get("summary", {})
    packet_index = index.get("packet_index", [])
    lines = [
        "# Workflow permission review packet index",
        "",
        "> Generated review evidence. No packet is a human decision or permission-change authorization.",
        "",
        f"- Packets: **{summary.get('packet_count', 0)}**",
        f"- Pending human review: **{summary.get('pending_human_review_count', 0)}**",
        f"- Human decisions recorded: **{summary.get('human_decision_recorded_count', 0)}**",
        f"- Machine recommendations: **{summary.get('machine_recommendation_count', 0)}**",
        f"- Bundle digest: `{index.get('bundle_digest', '')}`",
        "",
        "## Packets",
        "",
    ]
    if isinstance(packet_index, list):
        for item in packet_index:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('workflow', '')}` — `{item.get('review_id', '')}` — `{item.get('packet_digest', '')}`"
            )
    lines.append("")
    return "\n".join(lines)


def write_workflow_permission_review_packet_bundle(
    repo_root: str | Path,
    out_dir: str | Path,
    *,
    index: dict[str, Any] | None = None,
) -> dict[str, str]:
    root = Path(repo_root).resolve()
    output = Path(out_dir)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=True)

    payload = index or build_workflow_permission_review_packet_index(root)
    packets = payload.get("packets", [])
    if not isinstance(packets, list):
        packets = []

    for packet in packets:
        if not isinstance(packet, dict):
            continue
        review_id = str(packet.get("review_id", "unknown"))
        (output / f"{review_id}.json").write_text(
            json.dumps(packet, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output / f"{review_id}.md").write_text(render_packet_markdown(packet), encoding="utf-8")

    index_path = output / DEFAULT_INDEX_NAME
    markdown_index_path = output / DEFAULT_MARKDOWN_INDEX_NAME
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_index_path.write_text(render_index_markdown(payload), encoding="utf-8")
    return {
        "index_path": index_path.relative_to(root).as_posix()
        if index_path.is_relative_to(root)
        else index_path.as_posix(),
        "markdown_index_path": markdown_index_path.relative_to(root).as_posix()
        if markdown_index_path.is_relative_to(root)
        else markdown_index_path.as_posix(),
    }


def render_index_text(index: dict[str, Any]) -> str:
    summary = index.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return "\n".join(
        [
            f"packet_count={summary.get('packet_count', 0)}",
            f"pending_human_review_count={summary.get('pending_human_review_count', 0)}",
            f"human_decision_recorded_count={summary.get('human_decision_recorded_count', 0)}",
            f"machine_recommendation_count={summary.get('machine_recommendation_count', 0)}",
            f"bundle_digest={index.get('bundle_digest', '')}",
            "permission_mutation_allowed=false",
            "human_decision_fabrication_allowed=false",
            "merge_authorized=false",
        ]
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("review packet index must be a JSON object")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.workflow_permission_review_packet",
        description="Generate exact-digest workflow permission human-review packets.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir")
    parser.add_argument("--check-index")
    parser.add_argument("--fail-on-stale", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    index = build_workflow_permission_review_packet_index(ns.root)
    if ns.out_dir:
        write_workflow_permission_review_packet_bundle(ns.root, ns.out_dir, index=index)

    validation: dict[str, Any] | None = None
    if ns.check_index:
        root = Path(ns.root).resolve()
        check_path = Path(ns.check_index)
        if not check_path.is_absolute():
            check_path = root / check_path
        validation = validate_workflow_permission_review_packet_index(root, _load_json(check_path))

    output: dict[str, Any] = {"index": index}
    if validation is not None:
        output["freshness"] = validation

    if ns.format == "json":
        sys.stdout.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_index_text(index) + "\n")
        if validation is not None:
            sys.stdout.write(f"freshness_status={validation.get('status', 'unknown')}\n")
            reasons = validation.get("reasons", [])
            if isinstance(reasons, list):
                sys.stdout.write("freshness_reasons=" + json.dumps(reasons, sort_keys=True) + "\n")

    if ns.fail_on_stale and validation is not None and validation.get("fresh") is not True:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
