from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
SCHEMA_VERSION = "sdetkit.adaptive_diagnosis_export.v1"
AUTHORITY_FIELDS = (
    "reporting_only",
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def adaptive_diagnosis_card(model: JsonObject) -> JsonObject:
    card = _as_dict(model.get("adaptive_diagnosis"))
    if card:
        return card
    return _as_dict(_as_dict(model.get("primary_failure")).get("adaptive_diagnosis"))


def build_export(card: JsonObject) -> JsonObject:
    checks = {
        _text(name): bool(value)
        for name, value in _as_dict(card.get("checks")).items()
        if _text(name)
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "diagnosis": {
            "status": _text(card.get("status"), "review_first"),
            "failure_class": _text(card.get("failure_class"), "unknown"),
            "diagnostic_completeness": _text(card.get("diagnostic_completeness"), "insufficient"),
            "confidence": _text(card.get("confidence"), "low"),
            "review_first": bool(card.get("review_first", True)),
        },
        "evidence": {
            "checks": checks,
            "owner_files": [
                _text(item) for item in _as_list(card.get("owner_files")) if _text(item)
            ],
            "proof_commands": [
                _text(item) for item in _as_list(card.get("proof_commands")) if _text(item)
            ],
            "evidence_gaps": [
                _text(item) for item in _as_list(card.get("evidence_gaps")) if _text(item)
            ],
            "next_human_action": _text(
                card.get("next_human_action"),
                "Collect exact failure evidence before changing code.",
            ),
        },
        "authority": {field: bool(card.get(field, False)) for field in AUTHORITY_FIELDS},
    }


def export_from_model(model: JsonObject) -> JsonObject:
    card = adaptive_diagnosis_card(model)
    if not card:
        raise ValueError("review model has no adaptive diagnosis card")
    return build_export(card)


def serialize_export(payload: JsonObject) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the Adaptive Diagnosis contract as deterministic JSON."
    )
    parser.add_argument("--review-model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    model = json.loads(args.review_model.read_text(encoding="utf-8"))
    if not isinstance(model, dict):
        raise ValueError("review model must be a JSON object")
    payload = export_from_model(model)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(serialize_export(payload), encoding="utf-8", newline="\n")
    print("adaptive_diagnosis_json_export=passed")
    print(f"out={args.out.as_posix()}")
    print("reporting_only=true")
    print("automation_allowed=false")
    print("merge_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
