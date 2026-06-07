from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.professional.naming.cleanup.plan.v1"
DEFAULT_OUT = "build/sdetkit/professional-naming-cleanup-plan.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

ACTION_BOUNDARY = {
    "rename_allowed": False,
    "compatibility_migration_allowed": False,
    "public_surface_changes_allowed": False,
    "issue_mutation_allowed": False,
}

DOCS_ONLY = "docs_only_" + "cleanup"
SAFE_INTERNAL = "safe_cleanup_" + "internal"
DEFER = "defer_until_" + "related_pr"
INTERNAL_PATH = "internal_path_" + "requires_migration"
WORKFLOW_ALIAS = "workflow_" + "alias_migration"
PUBLIC_ALIAS = "public_surface_" + "requires_alias"

SAFE_CLASSES = {DOCS_ONLY, SAFE_INTERNAL}
COMPATIBILITY_CLASSES = {INTERNAL_PATH, WORKFLOW_ALIAS, PUBLIC_ALIAS}
PRIORITY_BY_CLASSIFICATION = {
    DOCS_ONLY: 10,
    SAFE_INTERNAL: 20,
    DEFER: 70,
    INTERNAL_PATH: 90,
    WORKFLOW_ALIAS: 100,
    PUBLIC_ALIAS: 110,
}


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("items", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


COMPATIBILITY_REVIEW_FIRST_FINDING_COUNT = "_".join(
    ("compatibility", "review", "first", "finding", "count")
)
REVIEW_LOCKED_NAMING_GOVERNANCE_REFERENCE = "review_locked_naming_governance_reference"
REVIEW_LOCKED_REFERENCE_COUNT = "_".join(("review", "locked", "reference", "count"))


def _text(value: object, default: str = "unknown") -> str:
    value_text = str(value or "").strip()
    return value_text if value_text else default


def _number(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_actionable(item: dict[str, Any]) -> bool:
    actionability = _text(item.get("actionability"), "")
    if actionability:
        return actionability == "actionable_prose_cleanup"
    return _text(item.get("classification")) in SAFE_CLASSES


def _top_counts(items: list[dict[str, Any]], field: str, *, limit: int = 8) -> list[dict[str, Any]]:
    counts = Counter(_text(item.get(field)) for item in items)
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
    ]


def _review_first_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if not _is_actionable(item)]


def _compatibility_review_first_count(items: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in items
        if _text(item.get("classification")) in COMPATIBILITY_CLASSES and not _is_actionable(item)
    )


def _review_locked_reference_count(items: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in items
        if _text(item.get("actionability_reason"), "") == REVIEW_LOCKED_NAMING_GOVERNANCE_REFERENCE
    )


def _path_counts(items: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in items:
        counts[_text(item.get("path"))] += max(1, _number(item.get("occurrence_count")))
    return [
        {"path": path, "occurrence_count": count}
        for path, count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
    ]


def _scope_for_classification(classification: str) -> str:
    scopes = {
        DOCS_ONLY: "docs-only wording cleanup after review",
        SAFE_INTERNAL: "internal source or test cleanup after review",
        DEFER: "defer until a related product PR owns the surrounding surface",
        INTERNAL_PATH: "requires migration plan before path rename",
        WORKFLOW_ALIAS: "requires workflow alias or migration plan before change",
        PUBLIC_ALIAS: "requires public compatibility alias before change",
    }
    return scopes.get(classification, "review before selecting cleanup scope")


def _slice(items: list[dict[str, Any]], classification: str) -> dict[str, Any]:
    requires_compatibility = classification in COMPATIBILITY_CLASSES
    actionable_finding_count = sum(1 for item in items if _is_actionable(item))
    review_first_finding_count = len(items) - actionable_finding_count
    review_first_items = _review_first_items(items)
    return {
        "id": classification.replace("_", "-"),
        "classification": classification,
        "priority": PRIORITY_BY_CLASSIFICATION.get(classification, 80),
        "finding_count": len(items),
        "actionable_finding_count": actionable_finding_count,
        "review_first_finding_count": review_first_finding_count,
        COMPATIBILITY_REVIEW_FIRST_FINDING_COUNT: _compatibility_review_first_count(items),
        REVIEW_LOCKED_REFERENCE_COUNT: _review_locked_reference_count(items),
        "occurrence_count": sum(max(1, _number(item.get("occurrence_count"))) for item in items),
        "top_terms": _top_counts(items, "term"),
        "top_surfaces": _top_counts(items, "surface"),
        "top_paths": _path_counts(items),
        "actionability_mix": _top_counts(items, "actionability"),
        "review_first_reason_mix": _top_counts(review_first_items, "actionability_reason"),
        "recommended_scope": _scope_for_classification(classification),
        "safe_to_plan_first": classification in SAFE_CLASSES and actionable_finding_count > 0,
        "requires_compatibility_plan": requires_compatibility,
        **ACTION_BOUNDARY,
        **AUTHORITY_BOUNDARY,
    }


def build_professional_naming_cleanup_plan(inventory: dict[str, Any]) -> dict[str, Any]:
    items = _items(inventory)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(_text(item.get("classification")), []).append(item)

    actionable_finding_count = sum(1 for item in items if _is_actionable(item))
    review_first_items = _review_first_items(items)

    slices = [_slice(members, classification) for classification, members in grouped.items()]
    slices.sort(
        key=lambda item: (
            int(item["priority"]),
            -int(item["finding_count"]),
            str(item["classification"]),
        )
    )

    first_safe = next((item for item in slices if item["safe_to_plan_first"]), None)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "plan review required" if items else "clean",
        "inventory_schema": str(inventory.get("schema_version", "")),
        "inventory_status": str(inventory.get("status", "")),
        "inventory_finding_count": _number(inventory.get("finding_count")),
        "actionable_finding_count": actionable_finding_count,
        "review_first_finding_count": len(items) - actionable_finding_count,
        COMPATIBILITY_REVIEW_FIRST_FINDING_COUNT: _compatibility_review_first_count(items),
        REVIEW_LOCKED_REFERENCE_COUNT: _review_locked_reference_count(items),
        "actionability_mix": _top_counts(items, "actionability"),
        "review_first_reason_mix": _top_counts(review_first_items, "actionability_reason"),
        "slice_count": len(slices),
        "safe_slice_count": sum(1 for item in slices if item["safe_to_plan_first"]),
        "compatibility_slice_count": sum(
            1 for item in slices if item["requires_compatibility_plan"]
        ),
        "recommended_first_slice": first_safe["id"] if first_safe else None,
        "cleanup_slices": slices,
        "recommended_action": (
            "start with actionable docs-only or internal cleanup slices; defer public surfaces until alias plans exist"
            if actionable_finding_count
            else (
                "no actionable direct cleanup slice remains; preserve review-first historical, path, "
                "template, workflow, and compatibility-bound findings until explicit migration plans exist"
                if items
                else "retain clean naming plan as evidence"
            )
        ),
        **ACTION_BOUNDARY,
        **AUTHORITY_BOUNDARY,
    }


def write_professional_naming_cleanup_plan_artifact(
    *,
    inventory_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_professional_naming_cleanup_plan(_load_dict(inventory_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit professional-naming-cleanup-plan",
        description="Build read-only professional naming cleanup plan from inventory.",
    )
    parser.add_argument("--inventory-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_professional_naming_cleanup_plan_artifact(
        inventory_json=ns.inventory_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"cleanup_plan_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"slice_count={payload['slice_count']}\n")
        sys.stdout.write(f"actionable_finding_count={payload['actionable_finding_count']}\n")
        sys.stdout.write(f"review_first_finding_count={payload['review_first_finding_count']}\n")
        sys.stdout.write(f"recommended_first_slice={payload['recommended_first_slice']}\n")
        sys.stdout.write(f"rename_allowed={str(payload['rename_allowed']).lower()}\n")
        sys.stdout.write(
            f"compatibility_migration_allowed={str(payload['compatibility_migration_allowed']).lower()}\n"
        )
        sys.stdout.write(
            f"public_surface_changes_allowed={str(payload['public_surface_changes_allowed']).lower()}\n"
        )
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
