from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.professional_naming_migration.v1"
DEFAULT_RENAME_MAP = "docs/naming/professional-naming-rename-map.json"
DEFAULT_OUT = "build/sdetkit/professional-naming-migration-plan.json"

SAFE_CONTENT_REWRITE = "safe_content_rewrite"
ALIAS_REQUIRED = "alias_required"
PRESERVE_HISTORY = "preserve_history"
TEMPLATE_LOCKED = "template_locked"
MANUAL_REVIEW = "manual_review"

MIGRATION_OR_ALIAS_REQUIRED = "migration_or_alias_required"
ACTIONABLE_PROSE = "actionable_prose_cleanup"

COMPATIBILITY_CLASSES = {
    "public_surface_requires_alias",
    "workflow_alias_migration",
    "internal_path_requires_migration",
}

PRESERVE_REASON_MARKERS = {
    "heading_or_chronology_label",
    "command_path_link_schema_or_audit_context",
    "table_or_generated_matrix",
}

TEMPLATE_LOCKED_PATHS = {
    "docs/integrations-release-prioritization-completion.md",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rename_map(payload: Mapping[str, Any]) -> dict[str, str]:
    raw = _as_dict(payload.get("rename_map"))
    return {_text(key): _text(value) for key, value in raw.items() if _text(key) and _text(value)}


def _migration_class(item: Mapping[str, Any]) -> str:
    path = _text(item.get("path"))
    classification = _text(item.get("classification"))
    actionability = _text(item.get("actionability"))
    reason = _text(item.get("actionability_reason"))
    match_type = _text(item.get("match_type"))

    if path in TEMPLATE_LOCKED_PATHS or "template_locked" in reason:
        return TEMPLATE_LOCKED

    if classification in COMPATIBILITY_CLASSES or actionability == MIGRATION_OR_ALIAS_REQUIRED:
        return ALIAS_REQUIRED

    if any(marker in reason for marker in PRESERVE_REASON_MARKERS):
        return PRESERVE_HISTORY

    if "/artifacts/" in path or path.startswith("docs/artifacts/"):
        return PRESERVE_HISTORY

    if actionability == ACTIONABLE_PROSE and match_type == "content":
        return SAFE_CONTENT_REWRITE

    return MANUAL_REVIEW


def _required_guard(migration_class: str) -> str:
    return {
        SAFE_CONTENT_REWRITE: "focused content proof",
        ALIAS_REQUIRED: "alias or compatibility shim plus tests",
        PRESERVE_HISTORY: "preserve historical evidence unless explicit migration plan exists",
        TEMPLATE_LOCKED: "template contract test must remain green",
        MANUAL_REVIEW: "human review before rename",
    }.get(migration_class, "human review before rename")


def build_professional_naming_migration_plan(
    inventory: Mapping[str, Any],
    rename_map_payload: Mapping[str, Any],
) -> dict[str, Any]:
    rename_map = _rename_map(rename_map_payload)
    rows: list[dict[str, Any]] = []

    for raw_item in _as_list(inventory.get("items")):
        item = _as_dict(raw_item)
        term = _text(item.get("term"))
        canonical = rename_map.get(
            term, _text(item.get("replacement_hint")) or "production_name_required"
        )
        migration_class = _migration_class(item)

        rows.append(
            {
                "term": term,
                "canonical_name": canonical,
                "path": _text(item.get("path")),
                "match_type": _text(item.get("match_type")),
                "classification": _text(item.get("classification")),
                "actionability": _text(item.get("actionability")),
                "actionability_reason": _text(item.get("actionability_reason")),
                "migration_class": migration_class,
                "allowed_to_apply": migration_class == SAFE_CONTENT_REWRITE,
                "required_guard": _required_guard(migration_class),
            }
        )

    by_class = Counter(row["migration_class"] for row in rows)
    safe_count = by_class.get(SAFE_CONTENT_REWRITE, 0)
    alias_count = by_class.get(ALIAS_REQUIRED, 0)

    if safe_count:
        recommended = "_".join(("apply", "safe", "content", "rewrite", "first"))
    elif alias_count:
        recommended = "_".join(("implement", "aliases", "before", "rename"))
    elif rows:
        recommended = "_".join(("review", "preserved", "history", "and", "manual", "contexts"))
    else:
        recommended = "_".join(("no", "migration", "items"))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "migration review required" if rows else "clean",
        "item_count": len(rows),
        "safe_content_rewrite_count": safe_count,
        "alias_required_count": alias_count,
        "preserve_history_count": by_class.get(PRESERVE_HISTORY, 0),
        "template_locked_count": by_class.get(TEMPLATE_LOCKED, 0),
        "manual_review_count": by_class.get(MANUAL_REVIEW, 0),
        "by_migration_class": dict(sorted(by_class.items())),
        "recommended_next_action": recommended,
        "blind_rename_allowed": False,
        "public_surface_change_without_alias": False,
        "workflow_rename_without_alias": False,
        "json_key_rename_without_alias": False,
        "artifact_slug_rename_without_redirect": False,
        "template_locked_rewrite": False,
        "items": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.professional_naming_migration")
    parser.add_argument("--inventory-json", required=True)
    parser.add_argument("--rename-map", default=DEFAULT_RENAME_MAP)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    try:
        inventory = _read_json(Path(args.inventory_json))
        rename_map_payload = _read_json(Path(args.rename_map))
        payload = build_professional_naming_migration_plan(inventory, rename_map_payload)
        _write_json(Path(args.out), payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"migration_plan_json={args.out}")
        print(f"status={payload['status']}")
        print(f"item_count={payload['item_count']}")
        print(f"safe_content_rewrite_count={payload['safe_content_rewrite_count']}")
        print(f"alias_required_count={payload['alias_required_count']}")
        print(f"preserve_history_count={payload['preserve_history_count']}")
        print(f"template_locked_count={payload['template_locked_count']}")
        print(f"manual_review_count={payload['manual_review_count']}")
        print(f"recommended_next_action={payload['recommended_next_action']}")
        print(f"blind_rename_allowed={str(payload['blind_rename_allowed']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
