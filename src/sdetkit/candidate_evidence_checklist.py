from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.candidate.evidence.checklist.v1"
DEFAULT_OUT = "build/sdetkit/candidate-evidence-checklist.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

EVIDENCE_GUIDANCE = {
    "issue collision review": {
        "category": "maintainer fit",
        "proof": "search open issues and PRs for overlapping work before selecting a lane",
    },
    "local proof feasibility": {
        "category": "environment quality",
        "proof": "record install, targeted tests, and expected offline blockers",
    },
    "scoped first PR card": {
        "category": "scope control",
        "proof": "write one minimal reviewable PR card with files, tests, and rollback",
    },
    "maintenance burden estimate": {
        "category": "maintenance risk",
        "proof": "estimate affected surfaces, churn risk, and long-term owner cost",
    },
    "public API risk review": {
        "category": "compatibility risk",
        "proof": "identify public surfaces and whether changes affect external users",
    },
    "candidate owner approval": {
        "category": "human gate",
        "proof": "record explicit human decision before freezing the candidate",
    },
}


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_bool(payload: dict[str, Any], key: str) -> bool:
    return bool(payload.get(key))


def _as_list(payload: dict[str, Any], key: str) -> list[str]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _evidence_item(name: str, missing: bool) -> dict[str, Any]:
    guidance = EVIDENCE_GUIDANCE.get(
        name,
        {
            "category": "candidate evidence",
            "proof": "record explicit proof before candidate freeze",
        },
    )
    return {
        "name": name,
        "category": guidance["category"],
        "status": "missing" if missing else "present",
        "required_before_freeze": True,
        "blocks_freeze": missing,
        "suggested_proof": guidance["proof"],
        **AUTHORITY_BOUNDARY,
    }


def build_candidate_evidence_checklist(readiness: dict[str, Any]) -> dict[str, Any]:
    required = _as_list(readiness, "required_evidence")
    missing = set(_as_list(readiness, "missing_evidence"))
    items = [_evidence_item(name, name in missing) for name in required]

    missing_count = sum(1 for item in items if item["status"] == "missing")
    present_count = len(items) - missing_count
    input_freeze_ready = _as_bool(readiness, "freeze_ready")
    input_candidate_frozen = _as_bool(readiness, "candidate_frozen")

    freeze_ready = False
    candidate_frozen = False
    status = "not ready" if missing_count else "ready for human freeze review"

    hard_blocks = list(_as_list(readiness, "hard_blocks"))
    if input_freeze_ready:
        hard_blocks.append("input readiness cannot authorize this checklist to freeze a candidate")
    if input_candidate_frozen:
        hard_blocks.append("input says candidate was frozen before checklist review")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "repo": str(readiness.get("repo", "unknown")),
        "commit": str(readiness.get("commit", "")),
        "readiness_schema": str(readiness.get("schema_version", "")),
        "readiness_status": str(readiness.get("status", "")),
        "candidate_frozen": candidate_frozen,
        "freeze_ready": freeze_ready,
        "required_item_count": len(items),
        "missing_item_count": missing_count,
        "present_item_count": present_count,
        "checklist_items": items,
        "hard_blocks": hard_blocks,
        "recommended_action": (
            "complete missing evidence before human freeze review"
            if missing_count
            else "perform human review before any candidate freeze"
        ),
        **AUTHORITY_BOUNDARY,
    }


def write_candidate_evidence_checklist_artifact(
    *,
    readiness_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_candidate_evidence_checklist(_load_dict(readiness_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit candidate-evidence-checklist",
        description="Build read-only candidate evidence checklist before any freeze decision.",
    )
    parser.add_argument("--readiness-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_candidate_evidence_checklist_artifact(
        readiness_json=ns.readiness_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"checklist_json={ns.out}\n")
        sys.stdout.write(f"repo={payload['repo']}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"missing_items={payload['missing_item_count']}\n")
        sys.stdout.write(f"freeze_ready={str(payload['freeze_ready']).lower()}\n")
        sys.stdout.write(f"candidate_frozen={str(payload['candidate_frozen']).lower()}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
