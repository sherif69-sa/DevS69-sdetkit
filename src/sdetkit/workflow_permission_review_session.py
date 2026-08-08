from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from .workflow_permission_decision_record import (
    SCHEMA_VERSION as DECISION_RECORD_SCHEMA_VERSION,
)
from .workflow_permission_decision_record import (
    authority_boundary as decision_record_authority_boundary,
)
from .workflow_permission_decision_record import validate_decision_record
from .workflow_permission_review_packet import build_workflow_permission_review_packet_index

SCHEMA_VERSION = "sdetkit.workflow_permission_review_session.v1"
CONTRACT_PATH = "docs/contracts/workflow-permission-review-session.v1.json"
GENERATOR_SOURCE_LABEL = "src/sdetkit/workflow_permission_review_session.py"
COMPILATION_MANIFEST_NAME = "workflow-permission-review-session-compilation.json"
ALLOWED_MODES = ("partial", "complete")
ALLOWED_DECISIONS = ("keep", "reduce", "split", "defer")

AUTHORITY_FIELDS = (
    "automation_allowed",
    "commit_allowed",
    "decision_inference_allowed",
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


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def session_digest(session: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json_bytes(session))


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timezone_aware(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _pending_packets(packet_index: dict[str, Any]) -> list[dict[str, Any]]:
    packets = packet_index.get("packets", [])
    if not isinstance(packets, list):
        return []
    pending: list[dict[str, Any]] = []
    for item in packets:
        if not isinstance(item, dict):
            continue
        boundary = item.get("decision_boundary", {})
        if not isinstance(boundary, dict) or boundary.get("human_decision_recorded") is not True:
            pending.append(item)
    return pending


def _session_entry_template(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": packet.get("review_id"),
        "packet_digest": packet.get("packet_digest"),
        "workflow": packet.get("workflow"),
        "workflow_sha256": packet.get("workflow_sha256"),
        "permission_group": packet.get("permission_group"),
        "decision": None,
        "rationale": None,
        "proposed_change": None,
        "proof_acknowledged": False,
        "rollback_acknowledged": False,
    }


def build_review_session_template(
    repo_root: str | Path = ".",
    *,
    mode: str = "complete",
) -> dict[str, Any]:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"unsupported session mode: {mode}")
    packet_index = build_workflow_permission_review_packet_index(repo_root)
    pending = _pending_packets(packet_index)
    entries = [_session_entry_template(packet) for packet in pending] if mode == "complete" else []
    return {
        "schema_version": SCHEMA_VERSION,
        "session_mode": mode,
        "packet_bundle_digest": packet_index.get("bundle_digest"),
        "packet_input_digest": packet_index.get("input_provenance", {}).get("input_digest"),
        "reviewer": None,
        "reviewer_evidence": None,
        "decided_at": None,
        "entries": entries,
        "authority_boundary": authority_boundary(),
    }


def _packet_maps(packet_index: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    pending = _pending_packets(packet_index)
    by_review_id = {str(packet.get("review_id", "")): packet for packet in pending}
    all_packets = packet_index.get("packets", [])
    all_review_ids = {
        str(packet.get("review_id", ""))
        for packet in all_packets
        if isinstance(packet, dict) and _nonempty_string(packet.get("review_id"))
    }
    return by_review_id, all_review_ids


def _compile_entry(
    session: dict[str, Any],
    entry: dict[str, Any],
    packet: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = {
        "schema_version": DECISION_RECORD_SCHEMA_VERSION,
        "review_id": packet.get("review_id"),
        "workflow": packet.get("workflow"),
        "workflow_sha256": packet.get("workflow_sha256"),
        "permission_group": packet.get("permission_group"),
        "decision": entry.get("decision"),
        "reviewer": session.get("reviewer"),
        "reviewer_evidence": session.get("reviewer_evidence"),
        "decided_at": session.get("decided_at"),
        "rationale": entry.get("rationale"),
        "proposed_change": entry.get("proposed_change"),
        "proof_contract": list(packet.get("proof_contract", [])),
        "rollback_contract": packet.get("rollback_contract"),
        "authority_boundary": decision_record_authority_boundary(),
    }
    review_entry = {
        "review_id": packet.get("review_id"),
        "workflow": packet.get("workflow"),
        "workflow_sha256": packet.get("workflow_sha256"),
        "permission_group": packet.get("permission_group"),
    }
    return record, validate_decision_record(record, review_entry)


def validate_review_session(
    repo_root: str | Path,
    session: dict[str, Any],
) -> dict[str, Any]:
    packet_index = build_workflow_permission_review_packet_index(repo_root)
    pending_by_review_id, all_review_ids = _packet_maps(packet_index)
    stale_reasons: list[str] = []
    invalid_reasons: list[str] = []

    if session.get("schema_version") != SCHEMA_VERSION:
        invalid_reasons.append("schema_version_mismatch")
    mode = session.get("session_mode")
    if mode not in ALLOWED_MODES:
        invalid_reasons.append("session_mode_invalid")
    if session.get("packet_bundle_digest") != packet_index.get("bundle_digest"):
        stale_reasons.append("packet_bundle_digest_mismatch")
    if session.get("packet_input_digest") != packet_index.get("input_provenance", {}).get(
        "input_digest"
    ):
        stale_reasons.append("packet_input_digest_mismatch")
    if pending_by_review_id and not _nonempty_string(session.get("reviewer")):
        invalid_reasons.append("reviewer_missing")
    reviewer_evidence = session.get("reviewer_evidence")
    if pending_by_review_id and not _nonempty_string(reviewer_evidence):
        invalid_reasons.append("reviewer_evidence_missing")
    elif pending_by_review_id and not str(reviewer_evidence).startswith("https://github.com/"):
        invalid_reasons.append("reviewer_evidence_must_be_github_url")
    if pending_by_review_id and not _timezone_aware(session.get("decided_at")):
        invalid_reasons.append("decided_at_invalid")
    if session.get("authority_boundary") != authority_boundary():
        invalid_reasons.append("authority_boundary_mismatch")

    entries = session.get("entries")
    if not isinstance(entries, list):
        invalid_reasons.append("entries_missing")
        entries = []
    if not entries and pending_by_review_id:
        invalid_reasons.append("session_has_no_review_entries")

    seen_review_ids: set[str] = set()
    compiled_candidates: list[dict[str, Any]] = []
    for offset, item in enumerate(entries):
        prefix = f"entry[{offset}]"
        if not isinstance(item, dict):
            invalid_reasons.append(f"{prefix}:entry_must_be_object")
            continue
        review_id = item.get("review_id")
        if not _nonempty_string(review_id):
            invalid_reasons.append(f"{prefix}:review_id_missing")
            continue
        review_id_text = str(review_id)
        if review_id_text in seen_review_ids:
            invalid_reasons.append(f"duplicate_review_id:{review_id_text}")
            continue
        seen_review_ids.add(review_id_text)

        packet = pending_by_review_id.get(review_id_text)
        if packet is None:
            if review_id_text in all_review_ids:
                invalid_reasons.append(f"review_already_decided:{review_id_text}")
            else:
                invalid_reasons.append(f"unknown_review_id:{review_id_text}")
            continue

        if item.get("packet_digest") != packet.get("packet_digest"):
            stale_reasons.append(f"packet_digest_mismatch:{review_id_text}")
        if item.get("workflow") != packet.get("workflow"):
            stale_reasons.append(f"workflow_mismatch:{review_id_text}")
        if item.get("workflow_sha256") != packet.get("workflow_sha256"):
            stale_reasons.append(f"workflow_digest_mismatch:{review_id_text}")
        if item.get("permission_group") != packet.get("permission_group"):
            stale_reasons.append(f"permission_group_mismatch:{review_id_text}")
        if item.get("proof_acknowledged") is not True:
            invalid_reasons.append(f"proof_not_acknowledged:{review_id_text}")
        if item.get("rollback_acknowledged") is not True:
            invalid_reasons.append(f"rollback_not_acknowledged:{review_id_text}")
        if item.get("decision") not in ALLOWED_DECISIONS:
            invalid_reasons.append(f"decision_invalid:{review_id_text}")

        record, record_validation = _compile_entry(session, item, packet)
        record_reasons = record_validation.get("reasons", [])
        if isinstance(record_reasons, list):
            for reason in record_reasons:
                invalid_reasons.append(f"decision_record_invalid:{review_id_text}:{reason}")
        compiled_candidates.append(
            {
                "review_id": review_id_text,
                "packet_digest": packet.get("packet_digest"),
                "record": record,
                "record_validation": record_validation,
            }
        )

    pending_ids = set(pending_by_review_id)
    missing_review_ids = sorted(pending_ids - seen_review_ids)
    if mode == "complete" and missing_review_ids:
        invalid_reasons.extend(
            f"complete_session_missing:{review_id}" for review_id in missing_review_ids
        )

    stale_reasons = sorted(set(stale_reasons))
    invalid_reasons = sorted(set(invalid_reasons))
    if invalid_reasons:
        status = "invalid"
    elif stale_reasons:
        status = "stale"
    else:
        status = "not_required" if not pending_by_review_id else "current"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "valid_current": status == "current",
        "stale": status == "stale",
        "session_digest": session_digest(session),
        "session_mode": mode,
        "packet_bundle_digest": packet_index.get("bundle_digest"),
        "pending_packet_count": len(pending_by_review_id),
        "submitted_entry_count": len(entries),
        "validated_entry_count": len(compiled_candidates),
        "missing_review_ids": missing_review_ids,
        "stale_reasons": stale_reasons,
        "invalid_reasons": invalid_reasons,
        "compiled_candidates": compiled_candidates if status == "current" else [],
        "authority_boundary": authority_boundary(),
    }


def compile_review_session(
    repo_root: str | Path,
    session: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_review_session(repo_root, session)
    if validation.get("valid_current") is not True:
        return {
            "status": ("not_required" if validation.get("status") == "not_required" else "blocked"),
            "validation": validation,
            "compiled_record_count": 0,
            "records": [],
            "manifest": None,
            "authority_boundary": authority_boundary(),
        }

    candidates = validation.get("compiled_candidates", [])
    records: list[dict[str, Any]] = []
    manifest_records: list[dict[str, Any]] = []
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            record = candidate.get("record")
            if not isinstance(record, dict):
                continue
            review_id = str(candidate.get("review_id", "unknown"))
            filename = f"{review_id}.decision.json"
            record_sha256 = _sha256_bytes(_canonical_json_bytes(record))
            records.append(
                {
                    "review_id": review_id,
                    "filename": filename,
                    "record_sha256": record_sha256,
                    "record": record,
                }
            )
            manifest_records.append(
                {
                    "review_id": review_id,
                    "filename": filename,
                    "record_sha256": record_sha256,
                    "packet_digest": candidate.get("packet_digest"),
                }
            )
    records.sort(key=lambda item: str(item.get("review_id", "")))
    manifest_records.sort(key=lambda item: str(item.get("review_id", "")))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "session_digest": validation.get("session_digest"),
        "session_mode": validation.get("session_mode"),
        "packet_bundle_digest": validation.get("packet_bundle_digest"),
        "compiled_record_count": len(records),
        "records": manifest_records,
        "source_tree_write_allowed": False,
        "canonical_decision_directory_write_allowed": False,
        "implementation_authorized": False,
        "authority_boundary": authority_boundary(),
    }
    return {
        "status": "compiled",
        "validation": validation,
        "compiled_record_count": len(records),
        "records": records,
        "manifest": manifest,
        "authority_boundary": authority_boundary(),
    }


def _safe_output_directory(repo_root: Path, out_dir: Path) -> Path:
    output = (repo_root / out_dir).resolve() if not out_dir.is_absolute() else out_dir.resolve()
    if output.is_relative_to(repo_root):
        relative = output.relative_to(repo_root)
        if not relative.parts or relative.parts[0] != "build":
            raise ValueError(
                "compiled decision records may only be written under build/ inside the repository"
            )
    return output


def write_compiled_decision_records(
    repo_root: str | Path,
    out_dir: str | Path,
    compilation: dict[str, Any],
) -> dict[str, Any]:
    if compilation.get("status") != "compiled":
        raise ValueError("cannot write blocked review-session compilation")
    root = Path(repo_root).resolve()
    output = _safe_output_directory(root, Path(out_dir))
    output.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    records = compilation.get("records", [])
    if isinstance(records, list):
        for item in records:
            if not isinstance(item, dict):
                continue
            record = item.get("record")
            filename = item.get("filename")
            if not isinstance(record, dict) or not isinstance(filename, str):
                continue
            path = output / filename
            path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written.append(path.as_posix())

    manifest = compilation.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("compiled review session is missing a manifest")
    manifest_path = output / COMPILATION_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "written_record_count": len(written),
        "written_records": written,
        "manifest_path": manifest_path.as_posix(),
        "source_tree_write_allowed": False,
        "authority_boundary": authority_boundary(),
    }


def render_validation_text(validation: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"status={validation.get('status', 'unknown')}",
            f"session_digest={validation.get('session_digest', '')}",
            f"session_mode={validation.get('session_mode', '')}",
            f"pending_packet_count={validation.get('pending_packet_count', 0)}",
            f"submitted_entry_count={validation.get('submitted_entry_count', 0)}",
            "stale_reasons=" + json.dumps(validation.get("stale_reasons", []), sort_keys=True),
            "invalid_reasons=" + json.dumps(validation.get("invalid_reasons", []), sort_keys=True),
            "decision_inference_allowed=false",
            "permission_mutation_allowed=false",
            "commit_allowed=false",
        ]
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("review session must be a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.workflow_permission_review_session",
        description="Validate and compile exact-digest batch human workflow-permission review sessions.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--template-out")
    parser.add_argument("--template-mode", choices=ALLOWED_MODES, default="complete")
    parser.add_argument("--session")
    parser.add_argument("--compile-out-dir")
    parser.add_argument("--fail-on-invalid", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(ns.root).resolve()
    result: dict[str, Any] = {"authority_boundary": authority_boundary()}
    exit_code = 0

    if ns.template_out:
        template = build_review_session_template(root, mode=ns.template_mode)
        template_path = Path(ns.template_out)
        if not template_path.is_absolute():
            template_path = root / template_path
        _write_json(template_path, template)
        result["template_path"] = template_path.as_posix()
        result["template"] = template

    if ns.session:
        session_path = Path(ns.session)
        if not session_path.is_absolute():
            session_path = root / session_path
        session = _load_json(session_path)
        compilation = compile_review_session(root, session)
        result["compilation"] = compilation
        validation = compilation.get("validation", {})
        if ns.compile_out_dir and compilation.get("status") == "compiled":
            result["write_result"] = write_compiled_decision_records(
                root,
                ns.compile_out_dir,
                compilation,
            )
        if ns.fail_on_invalid and (
            not isinstance(validation, dict) or validation.get("valid_current") is not True
        ):
            exit_code = 1

    if ns.format == "json":
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        compilation_value = result.get("compilation")
        if isinstance(compilation_value, dict):
            validation_value = compilation_value.get("validation")
            if isinstance(validation_value, dict):
                sys.stdout.write(render_validation_text(validation_value) + "\n")
            sys.stdout.write(
                f"compiled_record_count={compilation_value.get('compiled_record_count', 0)}\n"
            )
        elif "template" in result:
            template = result["template"]
            if isinstance(template, dict):
                entries = template.get("entries", [])
                count = len(entries) if isinstance(entries, list) else 0
                sys.stdout.write(f"template_mode={template.get('session_mode', '')}\n")
                sys.stdout.write(f"template_entry_count={count}\n")
                sys.stdout.write("decision_inference_allowed=false\n")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
