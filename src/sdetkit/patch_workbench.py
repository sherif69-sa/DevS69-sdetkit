from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .security import safe_path

SCHEMA_VERSION = "sdetkit.patch.workbench.v1"


def _risk_source(risk: dict[str, Any]) -> str:
    kind = str(risk.get("kind", "")).lower()
    file_path = str(risk.get("file", "")).lower()
    if "generated" in kind or "/build/" in file_path or file_path.startswith("build/"):
        if "release" in kind or "hygiene" in kind:
            return "generated-release-hygiene"
        return "generated-artifact"
    return "source"


def _candidate_id(item: dict[str, Any]) -> str:
    basis = "|".join(
        [
            str(item.get("title", "")),
            str(item.get("reason", "")),
            ",".join(sorted(str(x) for x in item.get("files", []) if isinstance(x, str))),
        ]
    )
    return "cand-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]


def build_workbench(payload: dict[str, Any], *, max_candidates: int) -> dict[str, Any]:
    diagnostics: list[str] = []
    source_risks = payload.get("source_risks", [])
    if not isinstance(source_risks, list):
        diagnostics.append("source_risks missing or not a list")
        source_risks = []
    patch_candidates = payload.get("patch_candidates", [])
    if not isinstance(patch_candidates, list):
        diagnostics.append("patch_candidates missing or not a list")
        patch_candidates = []

    validations = payload.get("validation_commands", payload.get("validation_plan", []))
    if not isinstance(validations, list):
        validations = []
    evidence = payload.get("evidence_paths", payload.get("evidence_files", []))
    if not isinstance(evidence, list):
        evidence = []

    risks_by_file: dict[str, dict[str, Any]] = {}
    for risk in source_risks:
        if not isinstance(risk, dict):
            continue
        src = _risk_source(risk)
        if src == "generated-artifact":
            continue
        key = str(risk.get("file", ""))
        if key and key not in risks_by_file:
            risks_by_file[key] = risk

    out_candidates: list[dict[str, Any]] = []
    for cand in patch_candidates:
        if not isinstance(cand, dict):
            continue
        files = [f for f in cand.get("files", []) if isinstance(f, str)]
        file_risks = [risks_by_file[f] for f in files if f in risks_by_file]
        primary_risk = file_risks[0] if file_risks else {}
        record = {
            "candidate_id": _candidate_id(cand),
            "title": str(cand.get("title", "patch candidate")),
            "files": files,
            "risk_source": "source" if primary_risk else "candidate-only",
            "confidence": "high" if primary_risk else "normal",
            "proposed_patch_strategy": str(cand.get("reason", "apply targeted minimal patch")),
            "validation_commands": [str(x) for x in validations],
            "evidence_references": [str(x) for x in evidence],
            "manual_review_notes": str(
                cand.get("expected_validation", "Review diffs and run validations.")
            ),
        }
        out_candidates.append(record)

    out_candidates = sorted(out_candidates, key=lambda x: (x["candidate_id"], x["title"]))[
        : max(0, max_candidates)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit patch workbench",
        "max_candidates": int(max_candidates),
        "candidate_count": len(out_candidates),
        "candidates": out_candidates,
        "diagnostics": diagnostics,
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [f"Patch workbench candidates: {payload.get('candidate_count', 0)}"]
    for cand in payload.get("candidates", []):
        lines.append(
            f"- {cand.get('candidate_id')} {cand.get('title')} files={','.join(cand.get('files', [])[:3])}"
        )
        lines.append(f"  strategy: {cand.get('proposed_patch_strategy')}")
        lines.append(f"  validate: {', '.join(cand.get('validation_commands', [])[:2])}")
    if payload.get("diagnostics"):
        lines.append("Diagnostics:")
        for d in payload["diagnostics"]:
            lines.append(f"- {d}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit patch workbench")
    p.add_argument("path")
    p.add_argument("--from-release-room", required=True)
    p.add_argument("--max-candidates", type=int, default=5)
    p.add_argument("--format", choices=["text", "operator-json"], default="text")
    ns = p.parse_args(argv)
    try:
        in_path = safe_path(Path.cwd(), str(ns.from_release_room), allow_absolute=True)
        raw = in_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "error": f"unreadable release-room input: {exc}",
                    "code": "PATCH_WORKBENCH_INPUT_UNREADABLE",
                },
                sort_keys=True,
            )
        )
        return 2
    try:
        source = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "error": f"invalid release-room JSON: {exc.msg}",
                    "code": "PATCH_WORKBENCH_INPUT_INVALID_JSON",
                },
                sort_keys=True,
            )
        )
        return 2

    result = build_workbench(source, max_candidates=int(ns.max_candidates))
    if ns.format == "operator-json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
