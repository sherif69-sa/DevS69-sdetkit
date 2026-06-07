from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.remediation_plan_engine import (
    ALLOWED_STRATEGY,
    BLOCKED_REASON,
    CLASSIFICATION,
    EXACT_FIX_SCOPE,
    EXECUTABLE_STRATEGIES,
    RISK_LEVEL,
    SAFE_TO_AUTO_FIX,
)

SCHEMA_VERSION = "sdetkit.patch_score.v1"
DEFAULT_OUT_DIR = Path("build") / "patch-scorer"
PATCH_SCORE_JSON = "patch-score.json"
PATCH_SCORE_MD = "patch-score.md"
DEFAULT_MINIMUM_SCORE = 80

JsonObject = dict[str, Any]

PROTECTED_EXACT_PATHS = {
    ".pre-commit-config.yaml",
    "ci.sh",
    "constraints-ci.txt",
    "pyproject.toml",
    "quality.sh",
    "sdetkit.policy.toml",
}
PROTECTED_PREFIXES = (
    ".github/",
    "tests/",
)


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _protected_path(path: str) -> bool:
    return path in PROTECTED_EXACT_PATHS or path.startswith(PROTECTED_PREFIXES)


def _select_plan(remediation_plan: Mapping[str, Any], diagnosis_id: str) -> JsonObject:
    plans = [_as_dict(item) for item in _as_list(remediation_plan.get("plans"))]
    if diagnosis_id:
        for plan in plans:
            if _string(plan.get("diagnosis_id")) == diagnosis_id:
                return plan
        return {}
    return plans[0] if plans else {}


def _history_safe_pattern_match(
    *,
    pattern_insights: Mapping[str, Any],
    classification: str,
    strategy: str,
) -> bool:
    for item in _as_list(pattern_insights.get("recurring_safe_fix_patterns")):
        pattern = _as_dict(item)
        if (
            _string(pattern.get("failure_class")) == classification
            and _string(pattern.get("action")) == strategy
        ):
            return True
    return False


def _history_review_surface_match(
    *,
    pattern_insights: Mapping[str, Any],
    surface: str,
) -> bool:
    for item in _as_list(pattern_insights.get("recurring_review_first_surfaces")):
        pattern = _as_dict(item)
        if _string(pattern.get("value")) == surface:
            return True
    return False


def _safety_gate_evidence(pattern_insights: Mapping[str, Any]) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    payload = _as_dict(pattern_insights.get("safety_gate_evidence"))
    if not payload:
        return {
            "collection_status": "not_collected",
            "status": "not_collected",
            "source": "pattern_insights.safety_gate_evidence",
            "record_count": 0,
            "review_first_count": 0,
            "safe_fix_allowed_count": 0,
            "reporting_only_count": 0,
            "report_paths": [],
            "expanded_authority_fields": [],
            "decision_boundary": denied,
        }

    boundary = _as_dict(payload.get("decision_boundary"))
    expanded = [key for key in denied if _bool(boundary.get(key))]
    return {
        "collection_status": _string(payload.get("collection_status")) or "collected",
        "status": _string(payload.get("status")) or "safety_gate_evidence_observed",
        "source": _string(payload.get("source")) or "pattern_insights.safety_gate_evidence",
        "record_count": int(payload.get("record_count", 0) or 0),
        "review_first_count": int(payload.get("review_first_count", 0) or 0),
        "safe_fix_allowed_count": int(payload.get("safe_fix_allowed_count", 0) or 0),
        "reporting_only_count": int(payload.get("reporting_only_count", 0) or 0),
        "report_paths": [
            _string(item) for item in _as_list(payload.get("report_paths")) if _string(item)
        ],
        "expanded_authority_fields": expanded,
        "decision_boundary": denied,
    }


def _risk_flag(
    code: str,
    message: str,
    *,
    blocking: bool,
    penalty: int,
    files: list[str] | None = None,
) -> JsonObject:
    return {
        "code": code,
        "message": message,
        "blocking": blocking,
        "penalty": penalty,
        "files": files or [],
    }


def _decision_reason(*, blocked: bool, candidate: bool) -> str:
    if blocked:
        return "Blocking safety signals require review-first handling."
    if candidate:
        return (
            "The patch stays inside an approved formatting-only scope; "
            "it is a candidate for future protected verification only."
        )
    return "The patch is not blocked, but its score is below the verification threshold."


STEP_ERROR_TAXONOMY_SCHEMA_VERSION = "sdetkit.step_error_taxonomy.v1"
STEP_ERROR_CATEGORIES = [
    "none",
    "scope_expansion",
    "skipped_proof",
    "unsafe_authority_request",
    "false_success_claim",
    "premature_completion",
    "wrong_helper_name",
    "wrong_marker_patch",
    "unsupported_helper_signature",
    "accidental_public_cli_drift",
    "authority_expansion_attempt",
    "skipped_post_format_proof",
]

OPERATOR_MISSTEP_CODE_TO_CATEGORY = {
    "wrong_helper_name": "wrong_helper_name",
    "wrong_marker_patch": "wrong_marker_patch",
    "unsupported_helper_signature": "unsupported_helper_signature",
    "accidental_public_cli_drift": "accidental_public_cli_drift",
    "authority_expansion_attempt": "authority_expansion_attempt",
    "skipped_post_format_proof": "skipped_post_format_proof",
}


def _int_from(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _operator_misstep_flags(proposed_patch: Mapping[str, Any]) -> list[JsonObject]:
    flags: list[JsonObject] = []
    for item in _as_list(proposed_patch.get("operator_missteps")):
        raw = _as_dict(item)
        code = _string(raw.get("code")).lower().strip()
        category = OPERATOR_MISSTEP_CODE_TO_CATEGORY.get(code)
        if not category and code in STEP_ERROR_CATEGORIES:
            category = code
        if not category:
            continue

        blocking = _bool(raw.get("blocking"))
        flag = _risk_flag(
            category.upper(),
            _string(raw.get("message")) or f"Operator misstep recorded: {category}.",
            blocking=blocking,
            penalty=_int_from(raw.get("penalty"), default=100 if blocking else 0),
            files=_string_list(raw.get("files")),
        )
        flag["step_error_category"] = category
        flag["source"] = "operator_misstep"
        flags.append(flag)
    return flags


def _authority_claimed(payload: Mapping[str, Any]) -> bool:
    return any(
        _bool(payload.get(key))
        for key in (
            "patch_application_allowed",
            "automation_allowed",
            "merge_authorized",
            "semantic_equivalence_proven",
        )
    )


def _flag_codes(flags: list[JsonObject]) -> set[str]:
    return {_string(flag.get("code")) for flag in flags if _string(flag.get("code"))}


def _step_error_taxonomy(flags: list[JsonObject]) -> JsonObject:
    codes = _flag_codes(flags)
    categories: list[str] = []
    if codes.intersection({"OUTSIDE_EXACT_FIX_SCOPE", "PROTECTED_PATH_CHANGED"}):
        categories.append("scope_expansion")
    if "PROOF_COMMANDS_MISSING" in codes:
        categories.append("skipped_proof")
    if "UNSAFE_AUTHORITY_REQUEST" in codes:
        categories.append("unsafe_authority_request")
    if "SAFETYGATE_EVIDENCE_AUTHORITY_VIOLATION" in codes:
        categories.append("authority_expansion_attempt")

    for flag in flags:
        category = _string(flag.get("step_error_category"))
        if category in STEP_ERROR_CATEGORIES and category not in categories:
            categories.append(category)

    return {
        "schema_version": STEP_ERROR_TAXONOMY_SCHEMA_VERSION,
        "supported_categories": STEP_ERROR_CATEGORIES,
        "observed_categories": categories,
        "primary_category": categories[0] if categories else "none",
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _dimension(status: str, score: int, reason: str) -> JsonObject:
    return {
        "status": status,
        "score": score,
        "reason": reason,
    }


def _outcome_dimensions(
    flags: list[JsonObject],
    *,
    changed_files: list[str],
    proof_commands: list[str],
    safe_pattern_match: bool,
) -> JsonObject:
    codes = _flag_codes(flags)
    blocked = any(_bool(flag.get("blocking")) for flag in flags)

    diagnostic_blocked = bool(
        codes.intersection({"PLAN_NOT_FOUND", "PLAN_REVIEW_FIRST", "NON_FORMATTING_SURFACE"})
    )
    scope_blocked = bool(
        codes.intersection(
            {"NO_CHANGED_FILES", "OUTSIDE_EXACT_FIX_SCOPE", "PROTECTED_PATH_CHANGED"}
        )
    )
    proof_blocked = "PROOF_COMMANDS_MISSING" in codes
    authority_blocked = "UNSAFE_AUTHORITY_REQUEST" in codes

    return {
        "diagnostic_precision": _dimension(
            "blocked" if diagnostic_blocked else "supported",
            0 if diagnostic_blocked else 100,
            "diagnosis and remediation plan are formatter-compatible"
            if not diagnostic_blocked
            else "diagnosis or remediation plan requires review-first handling",
        ),
        "patch_scope_safety": _dimension(
            "blocked" if scope_blocked else "contained",
            0 if scope_blocked else 100,
            "changed files stay inside the exact formatting scope"
            if not scope_blocked
            else "changed files are missing, protected, or outside the approved scope",
        ),
        "proof_strength": _dimension(
            "blocked"
            if proof_blocked
            else ("supported" if safe_pattern_match else "needs_more_history"),
            0 if proof_blocked else (100 if safe_pattern_match else 80),
            "required proof commands and repeated safe-fix history are present"
            if safe_pattern_match
            else (
                "required proof commands are missing"
                if proof_blocked
                else "proof commands exist, but repeated safe-fix history is not proven yet"
            ),
        ),
        "reviewability": _dimension(
            "reviewable" if changed_files and proof_commands else "thin_evidence",
            100 if changed_files and proof_commands else 50,
            "candidate exposes changed files and proof requirements for human review"
            if changed_files and proof_commands
            else "candidate evidence is missing changed files or proof requirements",
        ),
        "anti_cheat_integrity": _dimension(
            "blocked" if authority_blocked else "preserved",
            0 if authority_blocked else 100,
            "candidate does not claim patch, automation, merge, or semantic authority"
            if not authority_blocked
            else "candidate attempted to claim authority outside PatchScorer",
        ),
        "regression_risk": _dimension(
            "blocked" if blocked else ("low" if not codes else "watch"),
            0 if blocked else (100 if not codes else 90),
            "no blocking regression-risk signals were observed"
            if not blocked
            else "blocking safety signals require review-first handling",
        ),
    }


def score_patch(
    *,
    remediation_plan: Mapping[str, Any],
    proposed_patch: Mapping[str, Any],
    pattern_insights: Mapping[str, Any] | None = None,
    diagnosis_id: str = "",
    minimum_score: int = DEFAULT_MINIMUM_SCORE,
) -> JsonObject:
    if minimum_score < 0 or minimum_score > 100:
        msg = "minimum_score must be between 0 and 100"
        raise ValueError(msg)

    insights = _as_dict(pattern_insights)
    safety_gate_evidence = _safety_gate_evidence(insights)
    plan = _select_plan(remediation_plan, diagnosis_id)
    patch_id = _string(proposed_patch.get("patch_id")) or "proposed-patch"
    changed_files = _string_list(proposed_patch.get("changed_files"))
    proposed_authority_claimed = _authority_claimed(proposed_patch)
    flags: list[JsonObject] = []
    flags.extend(_operator_misstep_flags(proposed_patch))

    if proposed_authority_claimed:
        flags.append(
            _risk_flag(
                "UNSAFE_AUTHORITY_REQUEST",
                (
                    "PatchScorer input attempted to claim patch, automation, merge, "
                    "or semantic authority."
                ),
                blocking=True,
                penalty=100,
            )
        )

    expanded_safetygate_fields = _string_list(safety_gate_evidence.get("expanded_authority_fields"))
    if expanded_safetygate_fields:
        flags.append(
            _risk_flag(
                "SAFETYGATE_EVIDENCE_AUTHORITY_VIOLATION",
                "SafetyGate evidence attempted to expand PatchScorer authority.",
                blocking=True,
                penalty=100,
                files=expanded_safetygate_fields,
            )
        )

    if not plan:
        flags.append(
            _risk_flag(
                "PLAN_NOT_FOUND",
                "No remediation plan matched the proposed patch.",
                blocking=True,
                penalty=100,
            )
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "patch_id": patch_id,
            "diagnosis_id": diagnosis_id or "unknown",
            "changed_files": changed_files,
            "score": 0,
            "minimum_score": minimum_score,
            "risk_flags": flags,
            "dimensions": _outcome_dimensions(
                flags,
                changed_files=changed_files,
                proof_commands=[],
                safe_pattern_match=False,
            ),
            "step_error_taxonomy": _step_error_taxonomy(flags),
            "safety_gate_evidence": safety_gate_evidence,
            "decision": {
                "status": "blocked_review_first",
                "candidate_for_protected_verification": False,
                "automation_allowed": False,
                "reason": _decision_reason(blocked=True, candidate=False),
            },
            "proof_requirements": [],
            "history_evidence": {
                "safe_fix_pattern_match": False,
                "review_first_surface_match": False,
                "safety_gate_collection_status": _string(
                    safety_gate_evidence.get("collection_status")
                ),
                "safety_gate_safe_fix_allowed_count": int(
                    safety_gate_evidence.get("safe_fix_allowed_count", 0) or 0
                ),
                "safety_gate_review_first_count": int(
                    safety_gate_evidence.get("review_first_count", 0) or 0
                ),
            },
        }

    selected_diagnosis_id = _string(plan.get("diagnosis_id")) or diagnosis_id or "unknown"
    surface = _string(plan.get("failure_surface")) or "unknown"
    classification = _string(plan.get(CLASSIFICATION)) or "unknown"
    strategy = _string(plan.get(ALLOWED_STRATEGY)) or "unknown"
    exact_scope = _as_dict(plan.get(EXACT_FIX_SCOPE))
    allowed_files = _string_list(exact_scope.get("allowed_files")) or _string_list(
        plan.get("affected_files")
    )
    proof_commands = _string_list(plan.get("proof_commands"))

    if not _bool(plan.get(SAFE_TO_AUTO_FIX)):
        flags.append(
            _risk_flag(
                "PLAN_REVIEW_FIRST",
                _string(plan.get(BLOCKED_REASON))
                or "The remediation plan is not approved for automatic mutation.",
                blocking=True,
                penalty=100,
            )
        )

    if surface != "formatting":
        flags.append(
            _risk_flag(
                "NON_FORMATTING_SURFACE",
                f"Only formatting surface patches are eligible in this prototype; got {surface}.",
                blocking=True,
                penalty=100,
            )
        )

    if strategy not in EXECUTABLE_STRATEGIES:
        flags.append(
            _risk_flag(
                "STRATEGY_NOT_APPROVED",
                f"Strategy {strategy} is not an approved mechanical remediation strategy.",
                blocking=True,
                penalty=100,
            )
        )

    if not changed_files:
        flags.append(
            _risk_flag(
                "NO_CHANGED_FILES",
                "A patch cannot be scored as safe without explicit changed files.",
                blocking=True,
                penalty=100,
            )
        )

    outside_scope = sorted(set(changed_files) - set(allowed_files))
    if outside_scope:
        flags.append(
            _risk_flag(
                "OUTSIDE_EXACT_FIX_SCOPE",
                "The proposed patch changes files outside the remediation plan scope.",
                blocking=True,
                penalty=100,
                files=outside_scope,
            )
        )

    protected_files = [path for path in changed_files if _protected_path(path)]
    if protected_files:
        flags.append(
            _risk_flag(
                "PROTECTED_PATH_CHANGED",
                (
                    "Tests, workflow files, or gate/configuration files require "
                    "ProtectedVerifier before trust."
                ),
                blocking=True,
                penalty=100,
                files=protected_files,
            )
        )

    if not proof_commands:
        flags.append(
            _risk_flag(
                "PROOF_COMMANDS_MISSING",
                "The remediation plan does not provide required proof commands.",
                blocking=True,
                penalty=100,
            )
        )

    safe_pattern_match = _history_safe_pattern_match(
        pattern_insights=insights,
        classification=classification,
        strategy=strategy,
    )
    review_surface_match = _history_review_surface_match(
        pattern_insights=insights,
        surface=surface,
    )

    if review_surface_match:
        flags.append(
            _risk_flag(
                "RECURRING_REVIEW_FIRST_SURFACE",
                (
                    "Trajectory history records repeated review-first handling "
                    f"for the {surface} surface."
                ),
                blocking=True,
                penalty=100,
            )
        )
    elif not safe_pattern_match:
        flags.append(
            _risk_flag(
                "SAFE_PATTERN_NOT_REPEATED",
                "No repeated matching safe-fix pattern is proven in trajectory history yet.",
                blocking=False,
                penalty=10,
            )
        )

    score = max(0, 100 - sum(int(flag["penalty"]) for flag in flags))
    blocked = any(_bool(flag.get("blocking")) for flag in flags)
    candidate = not blocked and score >= minimum_score
    status = (
        "blocked_review_first"
        if blocked
        else ("candidate_for_protected_verification" if candidate else "needs_review")
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "patch_id": patch_id,
        "diagnosis_id": selected_diagnosis_id,
        "failure_surface": surface,
        "classification": classification,
        "risk_level": _string(plan.get(RISK_LEVEL)) or "unknown",
        "strategy": strategy,
        "changed_files": changed_files,
        "allowed_files": allowed_files,
        "score": score,
        "minimum_score": minimum_score,
        "risk_flags": flags,
        "dimensions": _outcome_dimensions(
            flags,
            changed_files=changed_files,
            proof_commands=proof_commands,
            safe_pattern_match=safe_pattern_match,
        ),
        "step_error_taxonomy": _step_error_taxonomy(flags),
        "safety_gate_evidence": safety_gate_evidence,
        "decision": {
            "status": status,
            "candidate_for_protected_verification": candidate,
            "automation_allowed": False,
            "reason": _decision_reason(blocked=blocked, candidate=candidate),
        },
        "proof_requirements": proof_commands,
        "history_evidence": {
            "safe_fix_pattern_match": safe_pattern_match,
            "review_first_surface_match": review_surface_match,
            "safety_gate_collection_status": _string(safety_gate_evidence.get("collection_status")),
            "safety_gate_safe_fix_allowed_count": int(
                safety_gate_evidence.get("safe_fix_allowed_count", 0) or 0
            ),
            "safety_gate_review_first_count": int(
                safety_gate_evidence.get("review_first_count", 0) or 0
            ),
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    decision = _as_dict(payload.get("decision"))
    history = _as_dict(payload.get("history_evidence"))
    safety_gate = _as_dict(payload.get("safety_gate_evidence"))
    safety_boundary = _as_dict(safety_gate.get("decision_boundary"))
    taxonomy = _as_dict(payload.get("step_error_taxonomy"))
    dimensions = _as_dict(payload.get("dimensions"))
    flags = [_as_dict(item) for item in _as_list(payload.get("risk_flags"))]

    lines = [
        "# Patch safety score",
        "",
        f"- Patch: `{_string(payload.get('patch_id'))}`",
        f"- Diagnosis: `{_string(payload.get('diagnosis_id'))}`",
        f"- Surface: `{_string(payload.get('failure_surface'))}`",
        f"- Classification: `{_string(payload.get('classification'))}`",
        f"- Strategy: `{_string(payload.get('strategy'))}`",
        f"- Score: `{int(payload.get('score', 0) or 0)}`",
        f"- Minimum score: `{int(payload.get('minimum_score', 0) or 0)}`",
        f"- Decision: `{_string(decision.get('status'))}`",
        f"- Step error primary category: `{_string(taxonomy.get('primary_category') or 'none')}`",
        "- Automation allowed: `false`",
        "",
        "## Outcome dimensions",
        "",
    ]
    for name in (
        "diagnostic_precision",
        "patch_scope_safety",
        "proof_strength",
        "reviewability",
        "anti_cheat_integrity",
        "regression_risk",
    ):
        dimension = _as_dict(dimensions.get(name))
        lines.append(
            f"- `{name}`: status=`{_string(dimension.get('status'))}` "
            f"score=`{int(dimension.get('score', 0) or 0)}`"
        )

    lines.extend(
        [
            "",
            "## History evidence",
            "",
            f"- Matching repeated safe-fix pattern: `{str(_bool(history.get('safe_fix_pattern_match'))).lower()}`",
            f"- Matching recurring review-first surface: `{str(_bool(history.get('review_first_surface_match'))).lower()}`",
            (
                "- SafetyGate evidence collection: "
                f"`{_string(history.get('safety_gate_collection_status'))}`"
            ),
            (
                "- SafetyGate safe-fix allowed records: "
                f"`{int(history.get('safety_gate_safe_fix_allowed_count', 0) or 0)}`"
            ),
            (
                "- SafetyGate review-first records: "
                f"`{int(history.get('safety_gate_review_first_count', 0) or 0)}`"
            ),
            "",
            "## SafetyGate evidence",
            "",
            f"- Collection status: `{_string(safety_gate.get('collection_status'))}`",
            f"- Status: `{_string(safety_gate.get('status'))}`",
            f"- Records: `{int(safety_gate.get('record_count', 0) or 0)}`",
            f"- Safe-fix allowed records: `{int(safety_gate.get('safe_fix_allowed_count', 0) or 0)}`",
            f"- Review-first records: `{int(safety_gate.get('review_first_count', 0) or 0)}`",
            f"- Reporting-only records: `{int(safety_gate.get('reporting_only_count', 0) or 0)}`",
            (
                "- Automation allowed by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('automation_allowed'))).lower()}`"
            ),
            (
                "- Patch application allowed by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (
                "- Merge authorized by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('merge_authorized'))).lower()}`"
            ),
            (
                "- Semantic equivalence proven by SafetyGate evidence: "
                f"`{str(_bool(safety_boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
            "## Risk flags",
            "",
        ]
    )

    if flags:
        for flag in flags:
            files = ", ".join(_string(item) for item in _as_list(flag.get("files")))
            suffix = f" files=`{files}`" if files else ""
            lines.append(
                f"- `{_string(flag.get('code'))}`: "
                f"blocking=`{str(_bool(flag.get('blocking'))).lower()}` "
                f"{_string(flag.get('message'))}{suffix}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Required proof", ""])
    proof = _string_list(payload.get("proof_requirements"))
    if proof:
        lines.extend(f"- `{command}`" for command in proof)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This score is read-only.",
            "- A candidate result does not authorize mutation or merge.",
            "- ProtectedVerifier must exist and pass before broader automation is trusted.",
            "",
        ]
    )
    return "\n".join(lines)


def write_patch_score(
    payload: Mapping[str, Any],
    *,
    out_dir: Path,
) -> dict[str, str]:
    json_path = out_dir / PATCH_SCORE_JSON
    markdown_path = out_dir / PATCH_SCORE_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return {
        "patch_score_json": json_path.as_posix(),
        "patch_score_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.patch_scorer")
    parser.add_argument("--remediation-plan", type=Path, required=True)
    parser.add_argument("--proposed-patch", type=Path, required=True)
    parser.add_argument("--pattern-insights", type=Path)
    parser.add_argument("--diagnosis-id", default="")
    parser.add_argument("--minimum-score", type=int, default=DEFAULT_MINIMUM_SCORE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        payload = score_patch(
            remediation_plan=_read_json(args.remediation_plan),
            proposed_patch=_read_json(args.proposed_patch),
            pattern_insights=_read_json(args.pattern_insights),
            diagnosis_id=args.diagnosis_id,
            minimum_score=args.minimum_score,
        )
        artifacts = write_patch_score(payload, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": artifacts,
                    "decision": payload["decision"],
                    "dimensions": payload["dimensions"],
                    "score": payload["score"],
                    "step_error_taxonomy": payload["step_error_taxonomy"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
