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
    plan = _select_plan(remediation_plan, diagnosis_id)
    patch_id = _string(proposed_patch.get("patch_id")) or "proposed-patch"
    changed_files = _string_list(proposed_patch.get("changed_files"))
    flags: list[JsonObject] = []

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
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    decision = _as_dict(payload.get("decision"))
    history = _as_dict(payload.get("history_evidence"))
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
        "- Automation allowed: `false`",
        "",
        "## History evidence",
        "",
        f"- Matching repeated safe-fix pattern: `{str(_bool(history.get('safe_fix_pattern_match'))).lower()}`",
        f"- Matching recurring review-first surface: `{str(_bool(history.get('review_first_surface_match'))).lower()}`",
        "",
        "## Risk flags",
        "",
    ]

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
                    "score": payload["score"],
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
