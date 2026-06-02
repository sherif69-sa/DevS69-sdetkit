from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.candidate.collision.checklist.v1"
DEFAULT_OUT = "build/sdetkit/candidate-collision-checklist.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

COLLISION_CHECKS = [
    {
        "name": "open issue overlap",
        "query_hint": "search open issues for the same bug, feature, or maintenance lane",
        "required_before_freeze": True,
    },
    {
        "name": "open pull request overlap",
        "query_hint": "search open pull requests for the same files, feature, or remediation plan",
        "required_before_freeze": True,
    },
    {
        "name": "recent merged work overlap",
        "query_hint": "search recently merged pull requests for already-completed equivalent work",
        "required_before_freeze": True,
    },
    {
        "name": "maintainer roadmap overlap",
        "query_hint": "review roadmap, milestones, labels, and project boards when available",
        "required_before_freeze": True,
    },
    {
        "name": "dependency or release timing conflict",
        "query_hint": "check active release, dependency, or migration work that could collide with the first PR",
        "required_before_freeze": True,
    },
    {
        "name": "first PR lane uniqueness",
        "query_hint": "confirm the proposed first PR is small, unique, and not already owned by another thread",
        "required_before_freeze": True,
    },
]


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_bool(payload: dict[str, Any], key: str) -> bool:
    return bool(payload.get(key))


def _as_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _has_missing_issue_collision(checklist: dict[str, Any]) -> bool:
    for item in _as_list(checklist, "checklist_items"):
        if str(item.get("name", "")).strip().lower() != "issue collision review":
            continue
        return str(item.get("status", "")).strip().lower() == "missing"
    return False


def _collision_item(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": template["name"],
        "status": "missing",
        "query_hint": template["query_hint"],
        "required_before_freeze": bool(template["required_before_freeze"]),
        "blocks_freeze": True,
        "evidence_required": "human-reviewed search evidence",
        **AUTHORITY_BOUNDARY,
    }


def build_candidate_collision_checklist(evidence_checklist: dict[str, Any]) -> dict[str, Any]:
    missing_issue_collision = _has_missing_issue_collision(evidence_checklist)
    items = [_collision_item(item) for item in COLLISION_CHECKS]
    missing_count = len(items)

    hard_blocks: list[str] = []
    if not missing_issue_collision:
        hard_blocks.append("input checklist does not show missing issue collision review")
    if _as_bool(evidence_checklist, "freeze_ready"):
        hard_blocks.append("input checklist cannot authorize candidate freeze")
    if _as_bool(evidence_checklist, "candidate_frozen"):
        hard_blocks.append("input checklist says candidate was already frozen")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "not ready",
        "repo": str(evidence_checklist.get("repo", "unknown")),
        "commit": str(evidence_checklist.get("commit", "")),
        "evidence_checklist_schema": str(evidence_checklist.get("schema_version", "")),
        "candidate_frozen": False,
        "freeze_ready": False,
        "missing_issue_collision_review": missing_issue_collision,
        "collision_check_count": len(items),
        "missing_collision_check_count": missing_count,
        "collision_checks": items,
        "hard_blocks": hard_blocks,
        "recommended_action": "complete human-reviewed collision searches before candidate freeze",
        **AUTHORITY_BOUNDARY,
    }


def write_candidate_collision_checklist_artifact(
    *,
    evidence_checklist_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_candidate_collision_checklist(_load_dict(evidence_checklist_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit candidate-collision-checklist",
        description="Build read-only candidate collision review checklist evidence.",
    )
    parser.add_argument("--evidence-checklist-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_candidate_collision_checklist_artifact(
        evidence_checklist_json=ns.evidence_checklist_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"collision_checklist_json={ns.out}\n")
        sys.stdout.write(f"repo={payload['repo']}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"collision_checks={payload['collision_check_count']}\n")
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
