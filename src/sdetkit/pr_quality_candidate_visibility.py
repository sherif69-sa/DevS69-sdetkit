from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit import (
    diagnostic_vector_engine,
    patch_scorer,
    protected_verifier,
    remediation_plan_engine,
)

SCHEMA_VERSION = "sdetkit.pr_quality.candidate_visibility.v1"
RESULT_JSON = "candidate-visibility.json"
RESULT_MD = "candidate-visibility.md"
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "candidate-visibility"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _read_changed_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(
        {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    )


def _candidate_files(plan: Mapping[str, Any]) -> list[str]:
    exact_scope = _as_dict(plan.get("exact_fix_scope"))
    return _string_list(exact_scope.get("allowed_files")) or _string_list(
        plan.get("affected_files")
    )


def _approved_formatting_candidate(record: Mapping[str, Any]) -> bool:
    safe_remediation = _as_dict(record.get("safe_remediation"))
    approved_strategies = {
        "run_pre_commit",
        "ruff_format",
        "eof_fixer",
        "trim_trailing_whitespace",
    }
    return (
        record.get("safe_to_auto_fix") is True
        and safe_remediation.get("safe_to_auto_fix") is True
        and _string(safe_remediation.get("category")).lower() == "formatting_only"
        and _string(safe_remediation.get("strategy")).lower() in approved_strategies
    )


def _read_only_candidate_record(record: Mapping[str, Any]) -> JsonObject:
    normalized = dict(record)
    if _approved_formatting_candidate(record):
        normalized["surface"] = "formatting"
    return normalized


def _read_only_candidate_intelligence(payload: Mapping[str, Any]) -> JsonObject:
    normalized = dict(payload)
    normalized["failed_checks"] = [
        _read_only_candidate_record(_as_dict(item))
        for item in _as_list(payload.get("failed_checks"))
    ]
    return normalized


def _read_only_candidate_action_report(payload: Mapping[str, Any]) -> JsonObject:
    normalized = dict(payload)
    primary = _as_dict(payload.get("primary_blocker"))
    if primary:
        normalized["primary_blocker"] = _read_only_candidate_record(primary)
    return normalized


def build_candidate_visibility(
    *,
    check_intelligence: Mapping[str, Any],
    evidence_graph: Mapping[str, Any],
    pr_quality_action_report: Mapping[str, Any],
    changed_files: list[str],
    pattern_insights: Mapping[str, Any],
    verification_evidence: Mapping[str, Any],
) -> JsonObject:
    diagnostic_vector = diagnostic_vector_engine.build_diagnostic_vector(
        check_intelligence=_read_only_candidate_intelligence(check_intelligence),
        evidence_graph=evidence_graph,
        pr_quality_action_report=_read_only_candidate_action_report(pr_quality_action_report),
    )
    remediation_plan = remediation_plan_engine.build_remediation_plan(diagnostic_vector)
    plans = [_as_dict(item) for item in _as_list(remediation_plan.get("plans")) if _as_dict(item)]
    candidates = [plan for plan in plans if plan.get("safe_to_auto_fix") is True]
    review_first = [plan for plan in plans if plan.get("safe_to_auto_fix") is not True]
    observed_pr_changed_files = sorted(set(changed_files))
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": "no_candidate",
        "candidate_count": len(candidates),
        "review_first_plan_count": len(review_first),
        "candidate_files": [],
        "observed_pr_changed_files": observed_pr_changed_files,
        "diagnostic_vector": diagnostic_vector,
        "remediation_plan": remediation_plan,
        "patch_score": {},
        "protected_verifier": {},
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": ("Candidate evidence is read-only and does not authorize mutation or merge."),
        },
    }

    if not candidates:
        return payload

    if len(candidates) != 1 or review_first:
        payload["status"] = "candidate_held_review_first"
        payload["decision_boundary"]["reason"] = (
            "Candidate evidence is mixed with review-first plans; "
            "no candidate verification is claimed."
        )
        return payload

    candidate = candidates[0]
    candidate_files = _candidate_files(candidate)
    payload["candidate_files"] = candidate_files
    score = patch_scorer.score_patch(
        remediation_plan=remediation_plan,
        proposed_patch={
            "patch_id": "pr-quality-read-only-candidate",
            "changed_files": candidate_files,
        },
        pattern_insights=pattern_insights,
        diagnosis_id=_string(candidate.get("diagnosis_id")),
    )
    verification = protected_verifier.verify_candidate(
        patch_score=score,
        verification_evidence=verification_evidence,
    )
    verification_decision = _as_dict(verification.get("decision"))
    structurally_verified = verification_decision.get("structural_verification_passed") is True
    payload["status"] = (
        "candidate_structurally_verified"
        if structurally_verified
        else "candidate_review_first_after_verification"
    )
    payload["patch_score"] = score
    payload["protected_verifier"] = verification
    payload["decision_boundary"]["reason"] = (
        "Structural evidence was observed, but semantic equivalence, "
        "automated mutation, and merge authorization remain unavailable."
        if structurally_verified
        else "ProtectedVerifier found blocking current evidence; "
        "the candidate remains review-first."
    )
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    candidate_count = int(payload.get("candidate_count", 0) or 0)
    boundary = _as_dict(payload.get("decision_boundary"))
    score = _as_dict(payload.get("patch_score"))
    score_decision = _as_dict(score.get("decision"))
    verification = _as_dict(payload.get("protected_verifier"))
    verification_decision = _as_dict(verification.get("decision"))
    candidate_files = _string_list(payload.get("candidate_files"))
    observed_files = _string_list(payload.get("observed_pr_changed_files"))
    lines = [
        "## Read-only remediation candidate verification",
        "",
        f"- Status: `{_string(payload.get('status') or 'unknown')}`",
        f"- Candidates observed: `{candidate_count}`",
        (f"- Review-first plans observed: `{int(payload.get('review_first_plan_count', 0) or 0)}`"),
        ("- Candidate scope: " + (", ".join(f"`{path}`" for path in candidate_files) or "none")),
        (
            "- Observed PR changed files: "
            + (", ".join(f"`{path}`" for path in observed_files) or "none")
        ),
        (f"- Automation allowed: `{str(bool(boundary.get('automation_allowed', False))).lower()}`"),
        (f"- Merge authorized: `{str(bool(boundary.get('merge_authorized', False))).lower()}`"),
        (
            "- Semantic equivalence proven: "
            f"`{str(bool(boundary.get('semantic_equivalence_proven', False))).lower()}`"
        ),
        f"- Boundary reason: {_string(boundary.get('reason') or 'none')}",
    ]

    if score:
        lines.extend(
            [
                f"- Patch score: `{int(score.get('score', 0) or 0)}`",
                (f"- PatchScorer decision: `{_string(score_decision.get('status') or 'unknown')}`"),
                "- PatchScorer automation allowed: `false`",
            ]
        )

    if verification:
        lines.extend(
            [
                (
                    "- ProtectedVerifier decision: "
                    f"`{_string(verification_decision.get('status') or 'unknown')}`"
                ),
                (
                    "- Structural verification passed: "
                    f"`{str(bool(verification_decision.get('structural_verification_passed', False))).lower()}`"
                ),
                "- ProtectedVerifier automation allowed: `false`",
                "- ProtectedVerifier merge authorized: `false`",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def write_visibility(payload: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result_json = out_dir / RESULT_JSON
    result_md = out_dir / RESULT_MD
    result_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result_md.write_text(render_markdown(payload), encoding="utf-8")

    paths = {
        "candidate_visibility_json": result_json.as_posix(),
        "candidate_visibility_markdown": result_md.as_posix(),
    }
    paths.update(
        diagnostic_vector_engine.write_diagnostic_vector(
            _as_dict(payload.get("diagnostic_vector")),
            out_dir / "diagnostic-vector",
        )
    )
    paths.update(
        remediation_plan_engine.write_remediation_plan(
            _as_dict(payload.get("remediation_plan")),
            out_dir / "remediation-plan",
        )
    )

    score = _as_dict(payload.get("patch_score"))
    if score:
        paths.update(patch_scorer.write_patch_score(score, out_dir=out_dir / "patch-score"))

    verification = _as_dict(payload.get("protected_verifier"))
    if verification:
        paths.update(
            protected_verifier.write_result(
                verification,
                out_dir=out_dir / "protected-verifier",
            )
        )

    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_candidate_visibility")
    parser.add_argument("--check-intelligence", type=Path, required=True)
    parser.add_argument("--evidence-graph", type=Path, required=True)
    parser.add_argument("--pr-quality-action-report", type=Path, required=True)
    parser.add_argument("--changed-files", type=Path, required=True)
    parser.add_argument("--pattern-insights", type=Path, required=True)
    parser.add_argument("--verification-evidence", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_candidate_visibility(
            check_intelligence=_read_json(args.check_intelligence),
            evidence_graph=_read_json(args.evidence_graph),
            pr_quality_action_report=_read_json(args.pr_quality_action_report),
            changed_files=_read_changed_files(args.changed_files),
            pattern_insights=_read_json(args.pattern_insights),
            verification_evidence=_read_json(args.verification_evidence),
        )
        artifacts = write_visibility(payload, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": artifacts,
                    "status": payload["status"],
                    "candidate_count": payload["candidate_count"],
                    "decision_boundary": payload["decision_boundary"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"status: {payload['status']}")
        print(f"candidate_count: {payload['candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
