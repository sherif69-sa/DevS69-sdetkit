from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.patch_plan.v1"
SOURCE_SCHEMA_VERSION = "sdetkit.adaptive.diagnosis.v1"
FAILURE_BUNDLE_SCHEMA_VERSION = "sdetkit.adaptive.failure_bundle.v1"
EVIDENCE_GRAPH_SCHEMA_VERSION = "sdetkit.evidence-graph.v1"
SUPPORTED_SOURCE_SCHEMAS = {
    SOURCE_SCHEMA_VERSION,
    FAILURE_BUNDLE_SCHEMA_VERSION,
    EVIDENCE_GRAPH_SCHEMA_VERSION,
}
SAFE_MECHANICAL_CODES = {"PRE_COMMIT_FORMAT_DRIFT", "RUFF_FIXABLE_LINT"}
ACTIONABLE_STATUSES = {"needs_fix", "needs_attention"}
_SEVERITY_PRIORITY = {"critical": 4, "high": 3, "warning": 2, "low": 1, "unknown": 0}
_SURFACE_PRIORITY = {
    "security": 9,
    "release": 8,
    "dependency": 7,
    "workflow": 6,
    "cli": 5,
    "docs": 4,
    "tests": 3,
    "quality": 2,
    "diagnostic_engine": 1,
    "unknown": 0,
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, limit: int = 300) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_diagnosis(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    schema = str(payload.get("schema_version", ""))
    if schema not in SUPPORTED_SOURCE_SCHEMAS:
        raise ValueError(f"unsupported adaptive patch-plan source schema in {path}")
    return _normalize_patch_plan_source(payload, path)


def _normalize_patch_plan_source(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    schema = str(payload.get("schema_version", ""))
    if schema == SOURCE_SCHEMA_VERSION:
        normalized = dict(payload)
        normalized.setdefault("source_kind", "adaptive_diagnosis")
        normalized.setdefault("source_schema_version", SOURCE_SCHEMA_VERSION)
        normalized.setdefault("source_artifacts", [path.as_posix()])
        return normalized

    if schema == FAILURE_BUNDLE_SCHEMA_VERSION:
        diagnoses = [_as_dict(item) for item in _as_list(payload.get("diagnoses"))]
        nested = _as_dict(payload.get("diagnosis"))
        if not diagnoses:
            diagnoses = [_as_dict(item) for item in _as_list(nested.get("diagnoses"))]
        return {
            "schema_version": SOURCE_SCHEMA_VERSION,
            "source_schema_version": schema,
            "source_kind": "failure_bundle",
            "source_artifacts": [path.as_posix()],
            "status": "needs_attention" if diagnoses else "monitor",
            "original_status": str(payload.get("status", "unknown")),
            "confidence": str(nested.get("confidence", payload.get("confidence", "unknown"))),
            "diagnoses": diagnoses,
            "evidence": [
                f"source_schema={schema}",
                f"source_path={path.as_posix()}",
                f"diagnosis_count={len(diagnoses)}",
            ],
        }

    nodes = [_as_dict(item) for item in _as_list(payload.get("nodes"))]
    nodes = [node for node in nodes if node]
    ranked_nodes = sorted(nodes, key=_graph_node_score, reverse=True)
    diagnoses = [_diagnosis_from_graph_node(node, path=path) for node in ranked_nodes]
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_schema_version": schema,
        "source_kind": "evidence_graph",
        "source_artifacts": [path.as_posix()],
        "status": "needs_attention" if diagnoses else "monitor",
        "confidence": "high" if diagnoses else "low",
        "diagnoses": diagnoses,
        "evidence": [
            f"source_schema={schema}",
            f"source_path={path.as_posix()}",
            f"graph_node_count={len(nodes)}",
        ],
    }


def _graph_node_score(node: dict[str, Any]) -> tuple[int, int, int]:
    surface = str(node.get("risk_surface", "unknown") or "unknown")
    severity = str(node.get("severity", "unknown") or "unknown")
    return (
        1 if bool(node.get("review_first", False)) else 0,
        _SEVERITY_PRIORITY.get(severity, 0),
        _SURFACE_PRIORITY.get(surface, 0),
    )


def _diagnosis_from_graph_node(node: dict[str, Any], *, path: Path) -> dict[str, Any]:
    surface = str(node.get("risk_surface", "unknown") or "unknown")
    finding_id = _safe_text(
        node.get("code") or node.get("diagnosis_code") or node.get("finding_id") or surface.upper(),
        80,
    )
    return {
        "code": finding_id,
        "title": _safe_text(node.get("title") or "Evidence graph finding", 160),
        "diagnosis": _safe_text(node.get("summary") or "Evidence Graph finding requires review."),
        "severity": _safe_text(node.get("severity") or "warning", 80),
        "confidence": "high" if bool(node.get("review_first", False)) else "medium",
        "affected_files": _as_list(node.get("owner_files")),
        "recommended_fix": _as_list(
            node.get("recommended_commands") or node.get("next_commands") or node.get("commands")
        ),
        "proof_commands": _as_list(node.get("proof_commands")),
        "evidence": [
            f"source_artifact={path.as_posix()}",
            f"risk_surface={surface}",
            f"operator_action={node.get('operator_action', 'review')}",
            f"automation_allowed_now={str(node.get('automation_allowed_now', False)).lower()}",
        ],
    }


def _first_diagnosis(payload: dict[str, Any]) -> dict[str, Any]:
    for item in _as_list(payload.get("diagnoses")):
        row = _as_dict(item)
        if row:
            return row
    return {}


def _candidate_scenarios(diagnosis: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _as_list(diagnosis.get("evidence")):
        text = str(item)
        if not text.startswith("candidate_scenarios="):
            continue
        for code in text.split("=", 1)[1].split(","):
            code = code.strip()
            if code and code not in out:
                out.append(code)
    return out


def _target_files(diagnosis: dict[str, Any]) -> list[str]:
    files = [_safe_text(value, 180) for value in _as_list(diagnosis.get("affected_files"))]
    return [value for value in files if value and "<" not in value and ">" not in value]


def _recommended_commands(diagnosis: dict[str, Any]) -> list[str]:
    commands = [
        _safe_text(value, 240)
        for value in _as_list(
            diagnosis.get("recommended_commands")
            or diagnosis.get("recommended_fix")
            or diagnosis.get("next_commands")
        )
    ]
    return [command for command in commands if command][:4]


def _proof_commands(diagnosis: dict[str, Any]) -> list[str]:
    commands = [_safe_text(value, 240) for value in _as_list(diagnosis.get("proof_commands"))]
    return [command for command in commands if command][:4]


def _confidence_meets_review_threshold(diagnosis: dict[str, Any]) -> bool:
    return str(diagnosis.get("confidence", "low")) in {"medium", "high"}


def _reproduction_available(diagnosis: dict[str, Any]) -> bool:
    return bool(_proof_commands(diagnosis))


def _patch_steps(diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    code = _safe_text(diagnosis.get("code") or "UNKNOWN", 80)
    files = _target_files(diagnosis) or ["<identify-from-first-proof>"]
    candidates = _candidate_scenarios(diagnosis)
    steps: list[dict[str, Any]] = [
        {
            "order": 1,
            "action": "reproduce",
            "target": _proof_commands(diagnosis)[:1] or ["<run-first-proof-command>"],
            "rationale": "Confirm the failure deterministically before proposing code changes.",
            "mutation_allowed": False,
        },
        {
            "order": 2,
            "action": "inspect_scope",
            "target": files,
            "rationale": "Limit review to the first failing file, traceback, or contract surface.",
            "mutation_allowed": False,
        },
        {
            "order": 3,
            "action": "draft_patch_hypothesis",
            "target": candidates[:3] or [code],
            "rationale": "Write a human-reviewed patch hypothesis tied to scenario evidence, not a broad rewrite.",
            "mutation_allowed": False,
        },
        {
            "order": 4,
            "action": "prove_after_patch",
            "target": _proof_commands(diagnosis) or ["<rerun-focused-proof>"],
            "rationale": "Any human-applied patch must be followed by the same focused proof commands.",
            "mutation_allowed": False,
        },
    ]
    return steps


def build_patch_plan(payload: dict[str, Any]) -> dict[str, Any]:
    diagnosis = _first_diagnosis(payload)
    code = _safe_text(diagnosis.get("code") or "UNKNOWN", 80)
    source_status = str(payload.get("status", "unknown"))
    confidence = str(diagnosis.get("confidence", payload.get("confidence", "unknown")))
    proof_commands = _proof_commands(diagnosis)
    actionable = bool(diagnosis) and source_status in ACTIONABLE_STATUSES
    mechanical = code in SAFE_MECHANICAL_CODES
    confidence_ready = _confidence_meets_review_threshold(diagnosis)
    reproduction_ready = _reproduction_available(diagnosis)
    plan_status = "review_required" if actionable and not mechanical else "not_applicable"
    if not diagnosis:
        reason = "No diagnosis was available to build an assisted patch plan."
    elif mechanical:
        reason = f"{code} is a safe mechanical diagnosis; use adaptive safe-fix planning instead."
    elif not actionable:
        reason = (
            f"source status {source_status} is not actionable enough for assisted patch planning."
        )
    else:
        reason = (
            f"{code} is not approved for automatic remediation; this is a review-only patch plan "
            "that preserves human ownership and proof-first sequencing."
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "status": plan_status,
        "source_status": source_status,
        "source_schema_version": str(
            payload.get("source_schema_version", payload.get("schema_version", "unknown"))
        ),
        "source_kind": str(payload.get("source_kind", "adaptive_diagnosis")),
        "source_code": code,
        "confidence": confidence,
        "safe_to_auto_fix": False,
        "dry_run_only": True,
        "requires_human_review": True,
        "reason": reason,
        "guardrails": {
            "deterministic_reproduction_required": True,
            "deterministic_reproduction_available": reproduction_ready,
            "scenario_confidence_threshold": "medium",
            "scenario_confidence_threshold_met": confidence_ready,
            "changed_file_scope_limit": "review identified files only",
            "post_fix_proof_required": True,
            "automation_mutation_allowed": False,
        },
        "candidate_scenarios": _candidate_scenarios(diagnosis),
        "affected_files": _target_files(diagnosis),
        "recommended_commands": _recommended_commands(diagnosis),
        "proof_commands": proof_commands,
        "source_artifacts": _as_list(payload.get("source_artifacts")),
        "patch_steps": [] if plan_status == "not_applicable" else _patch_steps(diagnosis),
        "rollback_notes": [
            "Keep changes in a small reviewable commit.",
            "If focused proof fails, revert the patch and record the diagnosis feedback event.",
        ],
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"status={payload['status']}",
        f"source_kind={payload.get('source_kind', 'adaptive_diagnosis')}",
        f"source_schema_version={payload.get('source_schema_version', 'unknown')}",
        f"source_code={payload['source_code']}",
        f"safe_to_auto_fix={str(payload['safe_to_auto_fix']).lower()}",
        f"requires_human_review={str(payload['requires_human_review']).lower()}",
        f"reason={payload['reason']}",
    ]
    for step in _as_list(payload.get("patch_steps")):
        row = _as_dict(step)
        lines.append(f"step={row.get('order')}|{row.get('action')}|mutation_allowed=false")
    return "\n".join(lines) + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive assisted patch plan",
        "",
        f"- Status: `{payload['status']}`",
        f"- Source kind: `{payload.get('source_kind', 'adaptive_diagnosis')}`",
        f"- Source schema: `{payload.get('source_schema_version', 'unknown')}`",
        f"- Source code: `{payload['source_code']}`",
        f"- Safe to auto-fix: `{str(payload['safe_to_auto_fix']).lower()}`",
        f"- Requires human review: `{str(payload['requires_human_review']).lower()}`",
        f"- Reason: {payload['reason']}",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in _as_dict(payload.get("guardrails")).items():
        lines.append(f"- `{key}`: `{str(value).lower() if isinstance(value, bool) else value}`")
    lines += ["", "## Review-only steps", ""]
    if not _as_list(payload.get("patch_steps")):
        lines.append("- No assisted patch steps are applicable for this diagnosis.")
    for step in _as_list(payload.get("patch_steps")):
        row = _as_dict(step)
        lines.append(
            f"{row.get('order')}. **{row.get('action')}** — {row.get('rationale')} "
            f"Mutation allowed: `{str(row.get('mutation_allowed')).lower()}`."
        )
    lines += ["", "## Proof commands", ""]
    for command in _as_list(payload.get("proof_commands")):
        lines.append(f"- `{command}`")
    if not _as_list(payload.get("proof_commands")):
        lines.append("- `<add-focused-proof-command>`")

    recommended = _as_list(payload.get("recommended_commands"))
    if recommended:
        lines += ["", "## Recommended review commands", ""]
        for command in recommended:
            lines.append(f"- `{command}`")

    return "\n".join(lines) + "\n"


def patch_plan_from_file(diagnosis_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    plan = build_patch_plan(_load_diagnosis(diagnosis_path))
    plan["source_path"] = diagnosis_path.as_posix()
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_patch_plan")
    parser.add_argument("diagnosis_json")
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = patch_plan_from_file(Path(args.diagnosis_json))
        if args.format == "json":
            rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
        elif args.format == "md":
            rendered = render_markdown(plan)
        else:
            rendered = render_text(plan)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
