from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.security.review.packet.v1"
DEFAULT_OUT = "build/sdetkit/security-review-packet.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

SECURITY_ACTION_BOUNDARY = {
    "dismiss_allowed": False,
    "suppress_allowed": False,
    "fix_allowed": False,
    "issue_mutation_allowed": False,
}

DECISION_OPTIONS = [
    "confirm false positive after human review",
    "open scoped remediation PR after human approval",
    "document suppression rationale after policy review",
    "request more evidence before disposition",
]


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _packet_status(inventory: dict[str, Any], matrix: dict[str, Any]) -> str:
    if str(inventory.get("status", "")) == "clean" and str(matrix.get("status", "")) == "clean":
        return "clean"
    return "human review required"


def _summary(inventory: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    source_count = inventory.get("source_count", {})
    source = source_count if isinstance(source_count, dict) else {}
    return {
        "inventory_status": str(inventory.get("status", "")),
        "matrix_status": str(matrix.get("status", "")),
        "source_error_count": _as_int(source.get("error")),
        "source_warn_count": _as_int(source.get("warn")),
        "source_info_count": _as_int(source.get("info")),
        "finding_count": _as_int(matrix.get("finding_count", inventory.get("actual_count", 0))),
        "matrix_row_count": _as_int(matrix.get("matrix_row_count")),
        "review_count": _as_int(inventory.get("review_count")),
    }


def _review_questions(matrix: dict[str, Any]) -> list[str]:
    rows = _as_list(matrix, "matrix_rows")
    if not rows:
        return ["Confirm the security snapshot is clean and no disposition is required."]

    questions = [
        "Does each candidate disposition have enough human-reviewed evidence?",
        "Is any finding a real remediation candidate rather than a false-positive candidate?",
        "Would any suppression require policy approval before implementation?",
        "Is a scoped remediation PR needed, and what file slice should it own?",
    ]
    dispositions = sorted({str(row.get("candidate_disposition", "")) for row in rows})
    if "false positive candidate" in dispositions:
        questions.append(
            "Can the false-positive candidate be justified without hiding a real issue?"
        )
    if "remediation candidate" in dispositions:
        questions.append("What minimal remediation PR proves the issue is resolved?")
    return questions


def _packet_sections(inventory: dict[str, Any], matrix: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": "inventory summary",
            "status": str(inventory.get("status", "")),
            "item_count": _as_int(inventory.get("actual_count")),
            "needs_human_review": _as_int(inventory.get("review_count")) > 0,
            **SECURITY_ACTION_BOUNDARY,
            **AUTHORITY_BOUNDARY,
        },
        {
            "name": "disposition matrix",
            "status": str(matrix.get("status", "")),
            "item_count": _as_int(matrix.get("matrix_row_count")),
            "needs_human_review": str(matrix.get("status", "")) != "clean",
            **SECURITY_ACTION_BOUNDARY,
            **AUTHORITY_BOUNDARY,
        },
        {
            "name": "human decision gate",
            "status": "required" if str(matrix.get("status", "")) != "clean" else "not required",
            "item_count": len(DECISION_OPTIONS),
            "needs_human_review": str(matrix.get("status", "")) != "clean",
            **SECURITY_ACTION_BOUNDARY,
            **AUTHORITY_BOUNDARY,
        },
    ]


def build_security_review_packet(
    inventory: dict[str, Any],
    matrix: dict[str, Any],
) -> dict[str, Any]:
    status = _packet_status(inventory, matrix)
    summary = _summary(inventory, matrix)
    decision_required = status != "clean"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "inventory_schema": str(inventory.get("schema_version", "")),
        "matrix_schema": str(matrix.get("schema_version", "")),
        "summary": summary,
        "packet_sections": _packet_sections(inventory, matrix),
        "matrix_rows": _as_list(matrix, "matrix_rows"),
        "review_questions": _review_questions(matrix),
        "decision_options": DECISION_OPTIONS,
        "decision_required": decision_required,
        "recommended_action": (
            "perform human security review before dismissal, suppression, or remediation"
            if decision_required
            else "retain clean packet as evidence"
        ),
        **SECURITY_ACTION_BOUNDARY,
        **AUTHORITY_BOUNDARY,
    }


def write_security_review_packet_artifact(
    *,
    inventory_json: str | Path,
    matrix_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_security_review_packet(_load_dict(inventory_json), _load_dict(matrix_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit security-review-packet",
        description="Build read-only human review packet from security triage artifacts.",
    )
    parser.add_argument("--inventory-json", required=True)
    parser.add_argument("--matrix-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_security_review_packet_artifact(
        inventory_json=ns.inventory_json,
        matrix_json=ns.matrix_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"review_packet_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"decision_required={str(payload['decision_required']).lower()}\n")
        sys.stdout.write(f"dismiss_allowed={str(payload['dismiss_allowed']).lower()}\n")
        sys.stdout.write(f"suppress_allowed={str(payload['suppress_allowed']).lower()}\n")
        sys.stdout.write(f"fix_allowed={str(payload['fix_allowed']).lower()}\n")
        sys.stdout.write(
            f"issue_mutation_allowed={str(payload['issue_mutation_allowed']).lower()}\n"
        )
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
