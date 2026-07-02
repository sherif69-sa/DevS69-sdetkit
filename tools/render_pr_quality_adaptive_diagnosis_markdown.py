from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


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


def _bullet_lines(values: object, *, empty: str) -> list[str]:
    items = [_text(item) for item in _as_list(values) if _text(item)]
    return [f"- `{item}`" for item in items] if items else [f"- {empty}"]


def render_adaptive_diagnosis_markdown(card: JsonObject) -> str:
    checks = _as_dict(card.get("checks"))
    check_lines = [
        f"- `{name}`: `{'pass' if bool(passed) else 'missing'}`" for name, passed in checks.items()
    ] or ["- No adaptive checks were emitted."]

    authority_fields = (
        "reporting_only",
        "automation_allowed",
        "patch_application_allowed",
        "security_dismissal_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    )
    authority_lines = [
        f"- `{field}={str(bool(card.get(field, False))).lower()}`" for field in authority_fields
    ]
    decision = "review_first" if bool(card.get("review_first", True)) else "actionable"

    lines = [
        "# Adaptive Diagnosis",
        "",
        "## Decision",
        "",
        f"- Completeness: `{_text(card.get('diagnostic_completeness'), 'insufficient')}`",
        f"- Confidence: `{_text(card.get('confidence'), 'low')}`",
        f"- Failure class: `{_text(card.get('failure_class'), 'unknown')}`",
        f"- Status: `{decision}`",
        "",
        "## Safeguards",
        "",
        *check_lines,
        "",
        "## Owner files",
        "",
        *_bullet_lines(card.get("owner_files"), empty="No owner file was resolved."),
        "",
        "## Focused proof",
        "",
        *_bullet_lines(
            card.get("proof_commands"),
            empty="No focused reproduction command was resolved.",
        ),
        "",
        "## Evidence gaps",
        "",
        *_bullet_lines(card.get("evidence_gaps"), empty="No evidence gaps were reported."),
        "",
        "## Next human action",
        "",
        _text(
            card.get("next_human_action"),
            "Collect exact failure evidence before changing code.",
        ),
        "",
        "## Authority boundary",
        "",
        *authority_lines,
        "",
    ]
    return "\n".join(lines)


def render_from_model(model: JsonObject) -> str:
    card = adaptive_diagnosis_card(model)
    if not card:
        raise ValueError("review model has no adaptive diagnosis card")
    return render_adaptive_diagnosis_markdown(card)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a contributor-facing Adaptive Diagnosis Markdown handoff."
    )
    parser.add_argument("--review-model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(args.review_model.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("review model must be a JSON object")
    rendered = render_from_model(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8", newline="\n")
    print("adaptive_diagnosis_markdown_render=passed")
    print(f"out={args.out.as_posix()}")
    print("reporting_only=true")
    print("automation_allowed=false")
    print("merge_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
