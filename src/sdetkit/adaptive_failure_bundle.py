from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import (
    adaptive_diagnosis,
    adaptive_diagnosis_memory,
    adaptive_patch_plan,
    adaptive_safe_fix,
    operator_brief,
    pr_quality_comment,
)

SCHEMA_VERSION = "sdetkit.adaptive.failure_bundle.v1"
MANIFEST_SCHEMA_VERSION = "sdetkit.adaptive.failure_bundle.manifest.v1"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _primary_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    diagnoses = [_as_dict(item) for item in _as_list(diagnosis.get("diagnoses"))]
    return diagnoses[0] if diagnoses else {}


def _learning_summary(db_path: Path) -> dict[str, Any]:
    if db_path.exists():
        return adaptive_diagnosis_memory.learning_summary_from_db(db_path)
    return adaptive_diagnosis_memory.summarize_learning_records([])


def _outcome_flags(
    *,
    proof_passed: bool,
    proof_failed: bool,
    fix_accepted: bool,
    fix_rejected: bool,
) -> tuple[bool | None, bool | None]:
    if proof_passed and proof_failed:
        raise ValueError("--proof-passed and --proof-failed are mutually exclusive")
    if fix_accepted and fix_rejected:
        raise ValueError("--fix-accepted and --fix-rejected are mutually exclusive")
    proof_result = True if proof_passed else False if proof_failed else None
    fix_result = True if fix_accepted else False if fix_rejected else None
    return proof_result, fix_result


def build_failure_bundle(
    *,
    log_path: Path,
    out_dir: Path,
    memory_db: Path | None = None,
    bundle_out: Path | None = None,
    proof_passed: bool = False,
    proof_failed: bool = False,
    fix_accepted: bool = False,
    fix_rejected: bool = False,
    false_positive: bool = False,
) -> dict[str, Any]:
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis = adaptive_diagnosis.analyze_evidence(log_text=log_text)
    primary = _primary_diagnosis(diagnosis)
    primary_code = str(primary.get("code", "") or "")
    review_first = primary_code in {"UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}

    diagnosis_path = out_dir / "adaptive-diagnosis.json"
    _write_json(diagnosis_path, diagnosis)

    comment_text = pr_quality_comment.render_adaptive_diagnosis_comment(diagnosis)
    comment_path = out_dir / "adaptive-diagnosis-comment.md"
    _write_text(comment_path, comment_text)

    db_path = memory_db or (out_dir / "adaptive-diagnosis-memory.jsonl")
    proof_result, fix_result = _outcome_flags(
        proof_passed=proof_passed,
        proof_failed=proof_failed,
        fix_accepted=fix_accepted,
        fix_rejected=fix_rejected,
    )
    records = adaptive_diagnosis_memory.build_learning_records(
        diagnosis,
        proof_passed=proof_result,
        fix_accepted=fix_result,
        false_positive=false_positive,
    )
    learning_record_summary: dict[str, Any] = {
        "db_path": db_path.as_posix(),
        "record_count": 0,
    }
    if records:
        learning_record_summary = adaptive_diagnosis_memory.append_learning_records(
            db_path, records
        )

    learning_summary = _learning_summary(db_path)
    learning_summary_path = out_dir / "adaptive-learning-summary.json"
    _write_json(learning_summary_path, learning_summary)

    safe_fix_path = out_dir / "adaptive-safe-fix-plan.json"
    safe_fix_plan = adaptive_safe_fix.plan_from_file(diagnosis_path, safe_fix_path)

    patch_plan_path = out_dir / "adaptive-patch-plan.json"
    patch_plan = adaptive_patch_plan.patch_plan_from_file(diagnosis_path, patch_plan_path)

    gate_ok = str(diagnosis.get("status", "")) in {"clear", "monitor"}
    gate = {
        "ok": gate_ok,
        "failed_steps": [] if gate_ok else [primary_code or "adaptive_diagnosis"],
    }
    brief_payload = operator_brief.build_operator_brief(
        gate=gate,
        diagnosis=diagnosis,
        learning_summary=learning_summary,
        safe_fix_plan=safe_fix_plan,
    )
    brief_json_path = out_dir / "operator-brief.json"
    brief_md_path = out_dir / "operator-brief.md"
    _write_json(brief_json_path, brief_payload)
    _write_text(brief_md_path, operator_brief.render_markdown(brief_payload))

    artifacts = {
        "diagnosis_json": diagnosis_path.as_posix(),
        "pr_comment_markdown": comment_path.as_posix(),
        "learning_db": db_path.as_posix(),
        "learning_summary_json": learning_summary_path.as_posix(),
        "safe_fix_plan_json": safe_fix_path.as_posix(),
        "patch_plan_json": patch_plan_path.as_posix(),
        "operator_brief_json": brief_json_path.as_posix(),
        "operator_brief_markdown": brief_md_path.as_posix(),
    }

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifacts": artifacts,
        "source_log": log_path.as_posix(),
        "primary_diagnosis_code": primary_code,
        "review_first": review_first,
        "safe_to_auto_fix": bool(safe_fix_plan.get("safe_to_auto_fix", False)),
    }
    manifest_path = out_dir / "artifact-manifest.json"
    _write_json(manifest_path, manifest)
    artifacts["artifact_manifest_json"] = manifest_path.as_posix()

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "source_log": log_path.as_posix(),
        "status": str(diagnosis.get("status", "unknown")),
        "primary_diagnosis_code": primary_code,
        "diagnosis_count": int(diagnosis.get("diagnosis_count", 0) or 0),
        "review_first": review_first,
        "safe_to_auto_fix": bool(safe_fix_plan.get("safe_to_auto_fix", False)),
        "artifacts": artifacts,
        "diagnosis": diagnosis,
        "learning_record_summary": learning_record_summary,
        "learning_summary": learning_summary,
        "safe_fix_plan": safe_fix_plan,
        "patch_plan": patch_plan,
        "operator_brief": brief_payload,
    }

    final_bundle_path = bundle_out or (out_dir / "failure-intelligence-bundle.json")
    _write_json(final_bundle_path, bundle)
    bundle["bundle_path"] = final_bundle_path.as_posix()
    _write_json(final_bundle_path, bundle)
    return bundle


def render_text(bundle: dict[str, Any]) -> str:
    artifacts = _as_dict(bundle.get("artifacts"))
    lines = [
        f"schema_version={bundle.get('schema_version')}",
        f"status={bundle.get('status')}",
        f"primary_diagnosis_code={bundle.get('primary_diagnosis_code')}",
        f"diagnosis_count={bundle.get('diagnosis_count')}",
        f"review_first={str(bundle.get('review_first')).lower()}",
        f"safe_to_auto_fix={str(bundle.get('safe_to_auto_fix')).lower()}",
        f"bundle_path={bundle.get('bundle_path', '')}",
    ]
    for key in sorted(artifacts):
        lines.append(f"artifact.{key}={artifacts[key]}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.adaptive_failure_bundle",
        description="Build a unified adaptive failure intelligence bundle from a log.",
    )
    parser.add_argument("--log", required=True, help="Failed CI or quality log to diagnose")
    parser.add_argument("--out-dir", default="build/sdetkit/failure-intelligence")
    parser.add_argument("--out", default="")
    parser.add_argument("--memory-db", default="")
    parser.add_argument("--proof-passed", action="store_true")
    parser.add_argument("--proof-failed", action="store_true")
    parser.add_argument("--fix-accepted", action="store_true")
    parser.add_argument("--fix-rejected", action="store_true")
    parser.add_argument("--false-positive", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        bundle = build_failure_bundle(
            log_path=Path(args.log),
            out_dir=Path(args.out_dir),
            memory_db=Path(args.memory_db) if args.memory_db else None,
            bundle_out=Path(args.out) if args.out else None,
            proof_passed=bool(args.proof_passed),
            proof_failed=bool(args.proof_failed),
            fix_accepted=bool(args.fix_accepted),
            fix_rejected=bool(args.fix_rejected),
            false_positive=bool(args.false_positive),
        )
    except Exception as exc:
        sys.stderr.write(f"adaptive failure-bundle: error: {exc}\n")
        return 2

    if args.format == "json":
        sys.stdout.write(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
