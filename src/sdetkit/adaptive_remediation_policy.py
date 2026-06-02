from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.remediation_policy.v1"
RESULT_SCHEMA_VERSION = "sdetkit.adaptive.remediation_policy.result.v1"
SAFE_FIX_SCHEMA_VERSION = "sdetkit.adaptive_safe_fix.v1"
PATCH_PLAN_SCHEMA_VERSION = "sdetkit.adaptive.patch_plan.v1"
DEFAULT_POLICY_PATH = "config/adaptive_remediation_policy.default.json"
SAFE_BUILT_IN_FIX_TYPES = {"format_only", "ruff_fixable_lint"}
UNSAFE_AUTO_FIX_TYPES = {"review_required", "unknown", "assisted_patch_plan"}
UNSAFE_AUTO_SOURCE_CODES = {"UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}
VALID_PROOF_OUTCOMES = {"proof_passed", "proof_failed", "reverted", "rejected"}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def default_policy() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "default-adaptive-remediation-policy",
        "allowed_safe_fix_types": sorted(SAFE_BUILT_IN_FIX_TYPES),
        "max_changed_files": 8,
        "required_proof_outcomes": ["proof_passed"],
        "allow_review_required_auto_fix": False,
        "blocked_auto_source_codes": sorted(UNSAFE_AUTO_SOURCE_CODES),
    }


def _policy_findings(policy: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if policy.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            {
                "code": "POLICY_SCHEMA_UNSUPPORTED",
                "severity": "high",
                "message": f"Policy schema must be {SCHEMA_VERSION}.",
            }
        )
    allowed_types = {str(item) for item in _as_list(policy.get("allowed_safe_fix_types"))}
    if not allowed_types:
        findings.append(
            {
                "code": "POLICY_ALLOWED_FIX_TYPES_EMPTY",
                "severity": "high",
                "message": "Policy must list at least one allowed safe-fix type.",
            }
        )
    unsafe_types = sorted(allowed_types.intersection(UNSAFE_AUTO_FIX_TYPES))
    if unsafe_types:
        findings.append(
            {
                "code": "POLICY_UNSAFE_FIX_TYPE_ALLOWED",
                "severity": "critical",
                "message": "Policy cannot allow review-required or unknown automatic fixes.",
                "evidence": unsafe_types,
            }
        )
    if bool(policy.get("allow_review_required_auto_fix")):
        findings.append(
            {
                "code": "POLICY_REVIEW_REQUIRED_" + "AUTO_FIX_ENABLED",
                "severity": "critical",
                "message": "Review-required diagnoses must remain human-owned.",
            }
        )
    max_changed_files = policy.get("max_changed_files")
    if not isinstance(max_changed_files, int) or isinstance(max_changed_files, bool):
        findings.append(
            {
                "code": "POLICY_CHANGED_FILE_SCOPE_INVALID",
                "severity": "high",
                "message": "max_changed_files must be an integer.",
            }
        )
    elif max_changed_files < 0:
        findings.append(
            {
                "code": "POLICY_CHANGED_FILE_SCOPE_NEGATIVE",
                "severity": "high",
                "message": "max_changed_files cannot be negative.",
            }
        )
    required_outcomes = {str(item) for item in _as_list(policy.get("required_proof_outcomes"))}
    if "proof_passed" not in required_outcomes:
        findings.append(
            {
                "code": "POLICY_PROOF_PASS_REQUIRED",
                "severity": "critical",
                "message": "Policy must require proof_passed before remediation signoff.",
            }
        )
    invalid_outcomes = sorted(required_outcomes.difference(VALID_PROOF_OUTCOMES))
    if invalid_outcomes:
        findings.append(
            {
                "code": "POLICY_PROOF_OUTCOME_INVALID",
                "severity": "high",
                "message": "Policy lists unsupported proof outcomes.",
                "evidence": invalid_outcomes,
            }
        )
    return findings


def _plan_kind(plan: dict[str, Any]) -> str:
    schema = str(plan.get("schema_version", ""))
    if schema == SAFE_FIX_SCHEMA_VERSION:
        return "safe_fix"
    if schema == PATCH_PLAN_SCHEMA_VERSION:
        return "assisted_patch_plan"
    return "unknown"


def _plan_findings(policy: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    plan_kind = _plan_kind(plan)
    safe_to_auto_fix = bool(plan.get("safe_to_auto_fix"))
    requires_human_review = bool(plan.get("requires_human_review", True))
    source_code = str(plan.get("source_code", "UNKNOWN") or "UNKNOWN")
    fix_type = str(plan.get("fix_type", plan.get("status", "unknown")) or "unknown")
    affected_files = [_safe_text(item) for item in _as_list(plan.get("affected_files"))]
    proof_commands = [_safe_text(item) for item in _as_list(plan.get("proof_commands"))]
    max_changed_files = int(policy.get("max_changed_files", 0))
    allowed_types = {str(item) for item in _as_list(policy.get("allowed_safe_fix_types"))}
    blocked_codes = {str(item) for item in _as_list(policy.get("blocked_auto_source_codes"))}
    blocked_codes.update(UNSAFE_AUTO_SOURCE_CODES)

    if plan_kind == "unknown":
        findings.append(
            {
                "code": "PLAN_SCHEMA_UNSUPPORTED",
                "severity": "high",
                "message": "Plan must be an adaptive safe-fix or assisted patch-plan artifact.",
            }
        )
        return findings

    if safe_to_auto_fix:
        if requires_human_review:
            findings.append(
                {
                    "code": "PLAN_AUTO_FIX_REQUIRES_REVIEW",
                    "severity": "critical",
                    "message": "Plans requiring human review cannot be automatic fixes.",
                }
            )
        if fix_type not in allowed_types:
            findings.append(
                {
                    "code": "PLAN_FIX_TYPE_NOT_ALLOWED",
                    "severity": "high",
                    "message": f"Fix type {fix_type} is not allowed by policy.",
                }
            )
        if source_code in blocked_codes:
            findings.append(
                {
                    "code": "PLAN_SOURCE_CODE_BLOCKED_FOR_AUTO_FIX",
                    "severity": "critical",
                    "message": f"Source code {source_code} cannot be auto-fixed.",
                }
            )
        if len(affected_files) > max_changed_files:
            findings.append(
                {
                    "code": "PLAN_CHANGED_FILE_SCOPE_EXCEEDED",
                    "severity": "high",
                    "message": "Plan changes more files than the policy permits.",
                    "evidence": {
                        "affected_file_count": len(affected_files),
                        "max_changed_files": max_changed_files,
                    },
                }
            )
        if not proof_commands:
            findings.append(
                {
                    "code": "PLAN_PROOF_COMMANDS_MISSING",
                    "severity": "critical",
                    "message": "Automatic fixes must include proof commands.",
                }
            )
    else:
        if plan_kind == "assisted_patch_plan" and not bool(plan.get("dry_run_only", False)):
            findings.append(
                {
                    "code": "PATCH_PLAN_NOT_DRY_RUN_ONLY",
                    "severity": "critical",
                    "message": "Assisted patch plans must remain dry-run-only.",
                }
            )
        if not requires_human_review:
            findings.append(
                {
                    "code": "REVIEW_REQUIRED_PLAN_NOT_HUMAN_OWNED",
                    "severity": "critical",
                    "message": "Non-auto remediation plans must require human review.",
                }
            )
    return findings


def evaluate_policy(policy: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    policy_findings = _policy_findings(policy)
    plan_findings = [] if policy_findings else _plan_findings(policy, plan)
    findings = policy_findings + plan_findings
    critical = [row for row in findings if row.get("severity") == "critical"]
    recommendation = "APPROVE"
    if policy_findings:
        recommendation = "REJECT_POLICY"
    elif plan_findings:
        recommendation = "REJECT_PLAN"
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ok": not findings,
        "recommendation": recommendation,
        "policy_name": str(policy.get("name", "unnamed")),
        "plan_kind": _plan_kind(plan),
        "source_code": str(plan.get("source_code", "UNKNOWN") or "UNKNOWN"),
        "fix_type": str(plan.get("fix_type", plan.get("status", "unknown")) or "unknown"),
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix")),
        "affected_file_count": len(_as_list(plan.get("affected_files"))),
        "finding_count": len(findings),
        "critical_finding_count": len(critical),
        "findings": findings,
        "next_owner_action": _next_owner_action(recommendation, findings),
    }


def _next_owner_action(recommendation: str, findings: list[dict[str, Any]]) -> str:
    if recommendation == "APPROVE":
        return "Policy allows this remediation plan; keep proof evidence before signoff."
    first = findings[0].get("code", "UNKNOWN") if findings else "UNKNOWN"
    if recommendation == "REJECT_POLICY":
        return f"Fix remediation policy before evaluating plans; first failure is {first}."
    return f"Keep remediation review-first; fix or narrow the plan before execution ({first})."


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"recommendation={payload['recommendation']}",
        f"plan_kind={payload['plan_kind']}",
        f"source_code={payload['source_code']}",
        f"fix_type={payload['fix_type']}",
        f"safe_to_auto_fix={str(payload['safe_to_auto_fix']).lower()}",
        f"finding_count={payload['finding_count']}",
        f"critical_finding_count={payload['critical_finding_count']}",
    ]
    for row in _as_list(payload.get("findings")):
        item = row if isinstance(row, dict) else {}
        lines.append(f"finding={item.get('severity')}|{item.get('code')}|{item.get('message')}")
    lines.append(f"next_owner_action={payload['next_owner_action']}")
    return "\n".join(lines) + "\n"


def _write_or_print(rendered: str, out: str) -> None:
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_remediation_policy")
    sub = parser.add_subparsers(dest="cmd", required=True)
    template = sub.add_parser("template", help="Print the default adaptive remediation policy")
    template.add_argument("--format", choices=["text", "json"], default="json")
    template.add_argument("--out", default="")
    validate = sub.add_parser("validate", help="Validate a remediation plan against policy")
    validate.add_argument("plan_json")
    validate.add_argument("--policy", default=DEFAULT_POLICY_PATH)
    validate.add_argument("--format", choices=["text", "json"], default="text")
    validate.add_argument("--out", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "template":
            policy = default_policy()
            rendered = (
                json.dumps(policy, indent=2, sort_keys=True) + "\n"
                if args.format == "json"
                else render_text(evaluate_policy(policy, {}))
            )
            _write_or_print(rendered, str(args.out))
            return 0
        policy = _load_json(Path(args.policy))
        plan = _load_json(Path(args.plan_json))
        payload = evaluate_policy(policy, plan)
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_text(payload)
        )
        _write_or_print(rendered, str(args.out))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
