from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .workflow_permission_review_packet import (
    build_workflow_permission_review_packet_index,
    render_packet_markdown,
)
from .workflow_permission_review_worklist import (
    build_workflow_permission_review_worklist,
    render_worklist_text,
)

SCHEMA_VERSION = "sdetkit.workflow_permission_review_handoff_bundle.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-review-handoff-bundle.v1.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_review_handoff_bundle.py"
DIGEST_ALGORITHM = "sha256"
MANIFEST_NAME = "workflow-permission-review-handoff-manifest.json"
WORKLIST_JSON_NAME = "workflow-permission-review-worklist.json"
WORKLIST_TEXT_NAME = "workflow-permission-review-worklist.txt"
README_NAME = "README.md"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "commit_allowed",
    "human_decision_fabrication_allowed",
    "implementation_authorized",
    "merge_authorized",
    "note_fabrication_allowed",
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


def _pretty_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


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


def _all_false_boundary(value: object) -> bool:
    return isinstance(value, dict) and bool(value) and not any(value.values())


def _active_packet_binding_reasons(
    work_item: dict[str, Any],
    packets: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    if len(packets) != 1:
        return None, ["packet_missing" if not packets else "duplicate_packets"]

    packet = packets[0]
    reasons: list[str] = []
    for field in ("review_id", "workflow", "workflow_sha256", "permission_group", "packet_digest"):
        if work_item.get(field) != packet.get(field):
            reasons.append(f"packet_binding_mismatch:{field}")

    if work_item.get("safe_to_patch") is not False:
        reasons.append("work_item_safe_to_patch_not_false")
    if not _all_false_boundary(work_item.get("authority_boundary")):
        reasons.append("work_item_authority_boundary_invalid")
    for field in ("machine_recommendation", "review_priority", "reviewer_assignment", "decision_prefill"):
        if work_item.get(field) is not None:
            reasons.append(f"work_item_machine_field_not_null:{field}")

    if packet.get("safe_to_patch") is not False:
        reasons.append("packet_safe_to_patch_not_false")
    if not _all_false_boundary(packet.get("authority_boundary")):
        reasons.append("packet_authority_boundary_invalid")

    return packet, sorted(set(reasons))


def workflow_permission_review_handoff_bundle_input_provenance(
    repo_root: str | Path = ".",
    *,
    worklist: dict[str, Any] | None = None,
    packet_index: dict[str, Any] | None = None,
    generator_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current_worklist = worklist or build_workflow_permission_review_worklist(root)
    current_packets = packet_index or build_workflow_permission_review_packet_index(root)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )

    worklist_provenance = current_worklist.get("input_provenance")
    packet_provenance = current_packets.get("input_provenance")
    if not isinstance(worklist_provenance, dict):
        worklist_provenance = {}
    if not isinstance(packet_provenance, dict):
        packet_provenance = {}

    inputs: list[tuple[str, bytes]] = [
        ("schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator.read_bytes()),
        (
            "review_worklist_input_digest",
            str(worklist_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        (
            "review_worklist_bundle_digest",
            str(current_worklist.get("bundle_digest", "")).encode("utf-8"),
        ),
        (
            "review_packet_input_digest",
            str(packet_provenance.get("input_digest", "")).encode("utf-8"),
        ),
        (
            "review_packet_bundle_digest",
            str(current_packets.get("bundle_digest", "")).encode("utf-8"),
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
        "review_worklist_input_digest": worklist_provenance.get("input_digest", ""),
        "review_worklist_bundle_digest": current_worklist.get("bundle_digest", ""),
        "review_packet_input_digest": packet_provenance.get("input_digest", ""),
        "review_packet_bundle_digest": current_packets.get("bundle_digest", ""),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "contract_path": CONTRACT_PATH,
    }


def render_handoff_markdown(
    worklist: dict[str, Any],
    packet_refs: list[dict[str, Any]],
) -> str:
    summary = worklist.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    lines = [
        "# Workflow permission reviewer handoff bundle",
        "",
        "> Offline evidence handoff only. This bundle does not recommend, rank, assign, decide, patch, mutate permissions, commit, merge, or dismiss security findings.",
        "",
        f"- Active work items: **{summary.get('work_item_count', 0)}**",
        f"- Human review actions: **{summary.get('review_action_count', 0)}**",
        f"- Implementation-plan actions: **{summary.get('implementation_action_count', 0)}**",
        f"- Repair actions: **{summary.get('blocked_repair_count', 0)}**",
        "",
        "## Included active packets",
        "",
    ]
    if packet_refs:
        for ref in packet_refs:
            lines.append(
                f"- `{ref.get('workflow', '')}` — action `{ref.get('next_human_action', '')}` — "
                f"JSON `{ref.get('json_path', '')}` — Markdown `{ref.get('markdown_path', '')}`"
            )
    else:
        lines.append("- No active reviewer packets are required.")
    lines.extend(
        [
            "",
            "## Human boundary",
            "",
            "Use the included packet evidence to perform the human review. Record any actual decision separately through Review Session v1 / Decision Record v1. This handoff bundle cannot prefill or retain that decision.",
            "",
            "## Authority boundary",
            "",
        ]
    )
    lines.extend(f"- `{field}=false`" for field in sorted(authority_boundary()))
    lines.append("")
    return "\n".join(lines)


def _build_file_payloads(
    worklist: dict[str, Any],
    packet_index: dict[str, Any],
) -> tuple[dict[str, bytes], list[dict[str, Any]], list[str]]:
    work_items = _dict_items(worklist.get("work_items"))
    packets = _dict_items(packet_index.get("packets"))
    packets_by_id = _index_by_review_id(packets)

    files: dict[str, bytes] = {
        WORKLIST_JSON_NAME: _pretty_json_bytes(worklist),
        WORKLIST_TEXT_NAME: render_worklist_text(worklist).encode("utf-8"),
    }
    packet_refs: list[dict[str, Any]] = []
    reasons: list[str] = []

    for item in work_items:
        review_id = str(item.get("review_id", ""))
        packet, binding_reasons = _active_packet_binding_reasons(
            item,
            packets_by_id.get(review_id, []),
        )
        reasons.extend(f"{review_id or 'unknown'}:{reason}" for reason in binding_reasons)
        if packet is None or binding_reasons:
            continue

        json_path = f"packets/{review_id}.json"
        markdown_path = f"packets/{review_id}.md"
        files[json_path] = _pretty_json_bytes(packet)
        files[markdown_path] = render_packet_markdown(packet).encode("utf-8")
        packet_refs.append(
            {
                "work_item_id": item.get("work_item_id"),
                "review_id": review_id,
                "workflow": item.get("workflow"),
                "workflow_sha256": item.get("workflow_sha256"),
                "permission_group": item.get("permission_group"),
                "lifecycle_state": item.get("lifecycle_state"),
                "next_human_action": item.get("next_human_action"),
                "packet_id": packet.get("packet_id"),
                "packet_digest": packet.get("packet_digest"),
                "json_path": json_path,
                "markdown_path": markdown_path,
            }
        )

    packet_refs.sort(key=lambda item: str(item.get("workflow", "")))
    reasons = sorted(set(reasons))
    files[README_NAME] = render_handoff_markdown(worklist, packet_refs).encode("utf-8")
    return files, packet_refs, reasons


def _artifact_index(files: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "sha256": _sha256_bytes(content),
            "byte_count": len(content),
            "kind": (
                "review_packet_json"
                if path.startswith("packets/") and path.endswith(".json")
                else (
                    "review_packet_markdown"
                    if path.startswith("packets/") and path.endswith(".md")
                    else "handoff_support"
                )
            ),
        }
        for path, content in sorted(files.items())
    ]


def _build_current_bundle(
    repo_root: str | Path = ".",
) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = Path(repo_root).resolve()
    worklist = build_workflow_permission_review_worklist(root)
    packet_index = build_workflow_permission_review_packet_index(root)
    files, packet_refs, binding_reasons = _build_file_payloads(worklist, packet_index)

    global_reasons: list[str] = []
    if worklist.get("status") == "blocked":
        global_reasons.append("review_worklist_blocked")
    elif worklist.get("status") not in {"human_work_required", "not_required"}:
        global_reasons.append("review_worklist_status_invalid")
    global_reasons.extend(binding_reasons)
    global_reasons = sorted(set(global_reasons))

    work_items = _dict_items(worklist.get("work_items"))
    if len(packet_refs) != len(work_items):
        global_reasons.append("active_packet_count_mismatch")
        global_reasons = sorted(set(global_reasons))

    artifacts = _artifact_index(files)
    provenance = workflow_permission_review_handoff_bundle_input_provenance(
        root,
        worklist=worklist,
        packet_index=packet_index,
    )
    digest_payload = {
        "artifact_index": artifacts,
        "packet_refs": packet_refs,
        "global_reasons": global_reasons,
        "review_worklist_bundle_digest": worklist.get("bundle_digest", ""),
    }
    bundle_digest = _sha256_bytes(_canonical_json_bytes(digest_payload))

    if global_reasons:
        status = "blocked"
    elif packet_refs:
        status = "ready_for_human_handoff"
    else:
        status = "not_required"

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "input_provenance": provenance,
        "summary": {
            "active_work_item_count": len(work_items),
            "packaged_packet_count": len(packet_refs),
            "artifact_count": len(artifacts),
            "blocked_reason_count": len(global_reasons),
            "machine_recommendation_count": 0,
            "machine_priority_count": 0,
            "automatic_reviewer_assignment_count": 0,
            "automatic_decision_count": 0,
            "automatic_permission_change_count": 0,
        },
        "global_reasons": global_reasons,
        "packet_refs": packet_refs,
        "artifact_index": artifacts,
        "bundle_digest": bundle_digest,
        "rules": {
            "active_work_items_only": True,
            "exact_current_packet_binding_required": True,
            "blocked_bundle_export_allowed": False,
            "retained_file_hash_validation_required": True,
            "machine_recommendation_allowed": False,
            "machine_priority_allowed": False,
            "automatic_reviewer_assignment_allowed": False,
            "automatic_decision_allowed": False,
            "workflow_mutation_allowed": False,
        },
        "authority_boundary": authority_boundary(),
    }
    return manifest, files


def build_workflow_permission_review_handoff_bundle(
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    manifest, _files = _build_current_bundle(repo_root)
    return manifest


def _safe_output_dir(root: Path, output: Path) -> Path:
    target = output.resolve() if output.is_absolute() else (root / output).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        return target
    if not relative.parts or relative.parts[0] != "build":
        raise ValueError("repository-local reviewer handoff output may only be written under build/")
    return target


def write_workflow_permission_review_handoff_bundle(
    repo_root: str | Path,
    out_dir: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    manifest, files = _build_current_bundle(root)
    if manifest.get("status") == "blocked":
        raise ValueError("blocked reviewer handoff bundle cannot be exported")

    output = _safe_output_dir(root, Path(out_dir))
    if output.exists() and any(output.iterdir()):
        raise ValueError("reviewer handoff output directory must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)

    for relative_path, content in sorted(files.items()):
        path = output / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (output / MANIFEST_NAME).write_bytes(_pretty_json_bytes(manifest))
    return manifest


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reviewer handoff manifest must be a JSON object")
    return payload


def validate_workflow_permission_review_handoff_bundle(
    repo_root: str | Path,
    bundle_dir: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    bundle = _safe_output_dir(root, Path(bundle_dir))
    manifest_path = bundle / MANIFEST_NAME
    reasons: list[str] = []
    if not manifest_path.is_file():
        return {
            "status": "stale",
            "fresh": False,
            "reasons": ["manifest_missing"],
            "authority_boundary": authority_boundary(),
        }

    recorded = _load_json(manifest_path)
    current, expected_files = _build_current_bundle(root)
    for field in (
        "schema_version",
        "status",
        "summary",
        "global_reasons",
        "packet_refs",
        "artifact_index",
        "bundle_digest",
    ):
        if recorded.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    recorded_provenance = recorded.get("input_provenance")
    current_provenance = current.get("input_provenance")
    if not isinstance(recorded_provenance, dict):
        recorded_provenance = {}
    if not isinstance(current_provenance, dict):
        current_provenance = {}
    if recorded_provenance.get("input_digest") != current_provenance.get("input_digest"):
        reasons.append("input_digest_mismatch")
    if recorded.get("authority_boundary") != authority_boundary():
        reasons.append("authority_boundary_mismatch")

    expected_paths = set(expected_files) | {MANIFEST_NAME}
    actual_paths = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    reasons.extend(f"artifact_missing:{path}" for path in missing)
    reasons.extend(f"artifact_unexpected:{path}" for path in unexpected)

    for relative_path, expected_content in sorted(expected_files.items()):
        path = bundle / relative_path
        if not path.is_file():
            continue
        actual_content = path.read_bytes()
        if actual_content != expected_content:
            reasons.append(f"artifact_content_mismatch:{relative_path}")
        if _sha256_bytes(actual_content) != _sha256_bytes(expected_content):
            reasons.append(f"artifact_digest_mismatch:{relative_path}")

    reasons = sorted(set(reasons))
    return {
        "status": "fresh" if not reasons else "stale",
        "fresh": not reasons,
        "reasons": reasons,
        "recorded_bundle_digest": recorded.get("bundle_digest", ""),
        "current_bundle_digest": current.get("bundle_digest", ""),
        "recorded_input_digest": recorded_provenance.get("input_digest", ""),
        "current_input_digest": current_provenance.get("input_digest", ""),
        "authority_boundary": authority_boundary(),
    }


def render_manifest_text(manifest: dict[str, Any]) -> str:
    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    return "\n".join(
        [
            "Workflow Permission Reviewer Handoff Bundle v1",
            f"status={manifest.get('status', 'unknown')}",
            f"active_work_item_count={summary.get('active_work_item_count', 0)}",
            f"packaged_packet_count={summary.get('packaged_packet_count', 0)}",
            f"artifact_count={summary.get('artifact_count', 0)}",
            f"blocked_reason_count={summary.get('blocked_reason_count', 0)}",
            f"bundle_digest={manifest.get('bundle_digest', '')}",
            "machine_recommendation_allowed=false",
            "review_assignment_allowed=false",
            "automatic_decision_allowed=false",
            "permission_mutation_allowed=false",
            "merge_authorized=false",
        ]
    ) + "\n"


def render_validation_text(validation: dict[str, Any]) -> str:
    reasons = validation.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    lines = [
        "Workflow Permission Reviewer Handoff Validation v1",
        f"status={validation.get('status', 'unknown')}",
        f"fresh={str(validation.get('fresh') is True).lower()}",
        f"reason_count={len(reasons)}",
        f"current_bundle_digest={validation.get('current_bundle_digest', '')}",
        "permission_mutation_allowed=false",
        "merge_authorized=false",
    ]
    lines.extend(f"reason={reason}" for reason in reasons)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or validate an offline workflow-permission reviewer handoff bundle"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir")
    parser.add_argument("--check-dir")
    parser.add_argument("--fail-on-stale", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.check_dir:
        validation = validate_workflow_permission_review_handoff_bundle(root, args.check_dir)
        if args.format == "json":
            print(json.dumps(validation, indent=2, sort_keys=True))
        else:
            print(render_validation_text(validation), end="")
        return 1 if args.fail_on_stale and not validation["fresh"] else 0

    manifest = build_workflow_permission_review_handoff_bundle(root)
    if args.out_dir:
        if manifest.get("status") == "blocked":
            if args.format == "json":
                print(json.dumps(manifest, indent=2, sort_keys=True))
            else:
                print(render_manifest_text(manifest), end="")
            return 1
        manifest = write_workflow_permission_review_handoff_bundle(root, args.out_dir)

    if args.format == "json":
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(render_manifest_text(manifest), end="")
    return 1 if manifest.get("status") == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
