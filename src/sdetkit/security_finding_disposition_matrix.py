from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.security.disposition.matrix.v1"
DEFAULT_OUT = "build/sdetkit/security-finding-disposition-matrix.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

SECURITY_ACTION_BOUNDARY = {
    "dismiss_allowed": False,
    "suppress_allowed": False,
    "fix_allowed": False,
}


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


def _norm(value: object, default: str = "unknown") -> str:
    text = str(value or "").strip()
    return text if text else default


def _candidate_disposition(item: dict[str, Any]) -> str:
    level = _norm(item.get("level")).lower()
    rule = _norm(item.get("rule")).upper()
    message = _norm(item.get("message"), "").lower()

    if level == "error":
        return "remediation candidate"
    if rule == "SEC_HIGH_ENTROPY_STRING":
        return "false positive candidate"
    if "allowlist" in message or "baseline" in message or "known accepted" in message:
        return "suppression candidate"
    return "review required"


def _recommended_action(disposition: str) -> str:
    if disposition == "remediation candidate":
        return "review and open a scoped remediation PR only after human confirmation"
    if disposition == "false positive candidate":
        return "review evidence before any dismissal decision"
    if disposition == "suppression candidate":
        return "review policy before any suppression decision"
    return "review finding before selecting a disposition"


def _group_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in items:
        key = (
            _norm(item.get("rule")),
            _norm(item.get("level")),
            _candidate_disposition(item),
        )
        grouped.setdefault(key, []).append(item)

    rows: list[dict[str, Any]] = []
    for (rule, level, disposition), members in grouped.items():
        path_counter = Counter(_norm(item.get("path")) for item in members)
        rows.append(
            {
                "rule": rule,
                "level": level,
                "candidate_disposition": disposition,
                "finding_count": len(members),
                "paths": [
                    {"path": path, "count": count}
                    for path, count in sorted(
                        path_counter.items(), key=lambda entry: (-entry[1], entry[0])
                    )
                ],
                "requires_human_review": True,
                "recommended_action": _recommended_action(disposition),
                **SECURITY_ACTION_BOUNDARY,
                **AUTHORITY_BOUNDARY,
            }
        )

    rows.sort(
        key=lambda row: (
            str(row["candidate_disposition"]) != "remediation candidate",
            str(row["candidate_disposition"]) != "review required",
            str(row["rule"]),
            str(row["level"]),
        )
    )
    return rows


def build_security_finding_disposition_matrix(inventory: dict[str, Any]) -> dict[str, Any]:
    items = _as_list(inventory, "items")
    rows = _group_rows(items)
    disposition_counts = Counter(str(row["candidate_disposition"]) for row in rows)

    if rows:
        status = "review required"
    elif str(inventory.get("status", "")) == "clean":
        status = "clean"
    else:
        status = "review required"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "inventory_schema": str(inventory.get("schema_version", "")),
        "inventory_status": str(inventory.get("status", "")),
        "source_count": inventory.get("source_count", {}),
        "finding_count": len(items),
        "matrix_row_count": len(rows),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "matrix_rows": rows,
        "recommended_action": "human review required before dismissal, suppression, or remediation",
        **SECURITY_ACTION_BOUNDARY,
        **AUTHORITY_BOUNDARY,
    }


def write_security_finding_disposition_matrix_artifact(
    *,
    inventory_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_security_finding_disposition_matrix(_load_dict(inventory_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit security-finding-disposition-matrix",
        description="Build read-only disposition matrix from a security findings inventory.",
    )
    parser.add_argument("--inventory-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_security_finding_disposition_matrix_artifact(
        inventory_json=ns.inventory_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"matrix_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"finding_count={payload['finding_count']}\n")
        sys.stdout.write(f"matrix_rows={payload['matrix_row_count']}\n")
        sys.stdout.write(f"dismiss_allowed={str(payload['dismiss_allowed']).lower()}\n")
        sys.stdout.write(f"suppress_allowed={str(payload['suppress_allowed']).lower()}\n")
        sys.stdout.write(f"fix_allowed={str(payload['fix_allowed']).lower()}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
