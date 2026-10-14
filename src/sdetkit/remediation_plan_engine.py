from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_vector_engine import (
    ACTUAL_FAILURE,
    AFFECTED_FILES,
    DIAGNOSIS_ID,
    FAILURE_SURFACE,
    HISTORY_CONTEXT,
    PROOF_COMMANDS,
    RECOMMENDED_NEXT_ACTION,
    REVIEW_FIRST,
    REVIEW_FIRST_REASON,
    SAFE_FIX_CANDIDATE,
)

SCHEMA_VERSION = "sdetkit.remediation_plan.v1"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"

PLAN_PART = "plan"
REMEDIATION_PART = "remediation"
JSON_PART = "json"
MD_PART = "md"

PLAN_JSON = f"{REMEDIATION_PART}-{PLAN_PART}.{JSON_PART}"
PLAN_MD = f"{REMEDIATION_PART}-{PLAN_PART}.{MD_PART}"
DEFAULT_OUT_DIR = str(Path("build") / REMEDIATION_PART)

CLASSIFICATION = "classification"
CONFIDENCE = "confidence"
SAFE_TO_AUTO_FIX = "_".join(("safe", "to", "auto", "fix"))
ALLOWED_STRATEGY = "_".join(("allowed", "strategy"))
BLOCKED_REASON = "_".join(("blocked", "reason"))
EXACT_FIX_SCOPE = "_".join(("exact", "fix", "scope"))
COMMANDS_TO_RUN = "_".join(("commands", "to", "run"))
HUMAN_REVIEW_ACTION = "_".join(("human", "review", "action"))
ROLLBACK_NOTES = "_".join(("rollback", "notes"))
RISK_LEVEL = "_".join(("risk", "level"))
REQUIRES_FRESH_LOGS = "_".join(("requires", "fresh", "logs"))
REQUIRES_SECURITY_REVIEW = "_".join(("requires", "security", "review"))
REQUIRES_RELEASE_VALIDATION = "_".join(("requires", "release", "validation"))

FORMAT_CLASSIFICATION = "_".join(("formatting", "only"))
TYPE_CLASSIFICATION = "_".join(("type", "contract"))
RUNTIME_CLASSIFICATION = "_".join(("runtime", "exception"))
RELEASE_CLASSIFICATION = "_".join(("release", "artifact"))
DEPENDENCY_CLASSIFICATION = "_".join(("dependency", "drift"))
SECURITY_CLASSIFICATION = "security"
DOCS_CLASSIFICATION = "_".join(("docs", "structural", "change"))
WORKFLOW_CLASSIFICATION = "_".join(("workflow", "contract"))
TEST_CLASSIFICATION = "_".join(("test", "contract"))
QUALITY_CLASSIFICATION = "_".join(("quality", "contract"))
UNKNOWN_CLASSIFICATION = "unknown"

STRATEGY_RUN_PRE_COMMIT = "_".join(("run", "pre", "commit"))
STRATEGY_RUFF_FORMAT = "_".join(("ruff", "format"))
STRATEGY_EOF_FIXER = "_".join(("eof", "fixer"))
STRATEGY_TRIM_WHITESPACE = "_".join(("trim", "trailing", "whitespace"))
STRATEGY_REVIEW_TYPE = "_".join(("review", "first", "type", "contract"))
STRATEGY_REVIEW_RUNTIME = "_".join(("review", "first", "runtime", "debug"))
STRATEGY_REVIEW_RELEASE = "_".join(("review", "first", "release", "validation"))
STRATEGY_REVIEW_DEPENDENCY = "_".join(("review", "first", "dependency", "alignment"))
STRATEGY_REVIEW_SECURITY = "_".join(("review", "first", "security", "review"))
STRATEGY_REVIEW_DOCS = "_".join(("review", "first", "docs", "contract"))
STRATEGY_REVIEW_WORKFLOW = "_".join(("review", "first", "workflow", "contract"))
STRATEGY_REVIEW_TEST = "_".join(("review", "first", "test", "contract"))
STRATEGY_REVIEW_QUALITY = "_".join(("review", "first", "quality", "contract"))
STRATEGY_COLLECT_LOGS = "_".join(("collect", "logs", "and", "classify"))

EXECUTABLE_STRATEGIES = {
    STRATEGY_RUN_PRE_COMMIT,
    STRATEGY_RUFF_FORMAT,
    STRATEGY_EOF_FIXER,
    STRATEGY_TRIM_WHITESPACE,
}

SURFACE_CLASSIFICATION = {
    "formatting": FORMAT_CLASSIFICATION,
    "type_contract": TYPE_CLASSIFICATION,
    "runtime": RUNTIME_CLASSIFICATION,
    "release": RELEASE_CLASSIFICATION,
    "dependency": DEPENDENCY_CLASSIFICATION,
    "security": SECURITY_CLASSIFICATION,
    "docs": DOCS_CLASSIFICATION,
    "workflow": WORKFLOW_CLASSIFICATION,
    "test": TEST_CLASSIFICATION,
    "quality": QUALITY_CLASSIFICATION,
    "unknown": UNKNOWN_CLASSIFICATION,
}

REVIEW_STRATEGY = {
    "type_contract": STRATEGY_REVIEW_TYPE,
    "runtime": STRATEGY_REVIEW_RUNTIME,
    "release": STRATEGY_REVIEW_RELEASE,
    "dependency": STRATEGY_REVIEW_DEPENDENCY,
    "security": STRATEGY_REVIEW_SECURITY,
    "docs": STRATEGY_REVIEW_DOCS,
    "workflow": STRATEGY_REVIEW_WORKFLOW,
    "test": STRATEGY_REVIEW_TEST,
    "quality": STRATEGY_REVIEW_QUALITY,
    "unknown": STRATEGY_COLLECT_LOGS,
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _string_list(value: Any) -> list[str]:
    values = _as_list(value)
    return sorted({_string(item) for item in values if _string(item)})


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _classification(surface: str) -> str:
    return SURFACE_CLASSIFICATION.get(surface, UNKNOWN_CLASSIFICATION)


def _review_strategy(surface: str) -> str:
    return REVIEW_STRATEGY.get(surface, STRATEGY_COLLECT_LOGS)


def _is_formatting_executable(diagnosis: Mapping[str, Any]) -> bool:
    surface = _string(diagnosis.get(FAILURE_SURFACE))
    return (
        surface == "formatting"
        and _bool(diagnosis.get(SAFE_FIX_CANDIDATE))
        and not _bool(diagnosis.get(REVIEW_FIRST))
    )


def _strategy_for_executable_formatting(diagnosis: Mapping[str, Any]) -> str:
    recommended = _string(diagnosis.get(RECOMMENDED_NEXT_ACTION))
    if recommended in EXECUTABLE_STRATEGIES:
        return recommended
    return STRATEGY_RUN_PRE_COMMIT


def _commands_for_strategy(strategy: str, proof_commands: list[str]) -> list[str]:
    if strategy == STRATEGY_RUN_PRE_COMMIT:
        return ["python -m pre_commit run -a"]
    if strategy == STRATEGY_RUFF_FORMAT:
        return ["python -m ruff format ."]
    if strategy == STRATEGY_EOF_FIXER:
        return ["python -m pre_commit run end-of-file-fixer -a"]
    if strategy == STRATEGY_TRIM_WHITESPACE:
        return ["python -m pre_commit run trailing-whitespace -a"]
    return proof_commands


def _blocked_reason(surface: str, diagnosis: Mapping[str, Any]) -> str:
    explicit = _string(diagnosis.get(REVIEW_FIRST_REASON))
    if explicit:
        return explicit
    if surface == "security":
        return "security findings require human review"
    if surface == "release":
        return "release artifacts require clean build and metadata validation"
    if surface == "dependency":
        return "dependency drift requires human dependency alignment"
    if surface == "runtime":
        return "runtime failures require human debugging"
    if surface == "type_contract":
        return "type contract failures require human review"
    if surface == "unknown":
        return "unknown failures require fresh logs and classification"
    if surface in {"docs", "workflow", "test", "quality"}:
        return f"{surface} changes remain review-first"
    return "not approved for automatic mutation"


def _human_review_action(surface: str, diagnosis: Mapping[str, Any]) -> str:
    actual = _string(diagnosis.get(ACTUAL_FAILURE))
    if surface == "formatting":
        return "review deterministic formatter output before merge"
    if surface == "release":
        return "rebuild package artifacts from a clean workspace and run twine check"
    if surface == "security":
        return "review security evidence and do not dismiss findings automatically"
    if surface == "dependency":
        return "review dependency evidence and align constraints manually"
    if surface == "type_contract":
        return "review the type contract and preserve public compatibility"
    if surface == "runtime":
        return "debug the runtime exception from the first failing line"
    if surface == "unknown":
        return "collect failed check logs and classify the first real failure"
    return f"review {surface} failure: {actual}" if actual else f"review {surface} failure"


def _risk_level(surface: str, executable: bool) -> str:
    if executable and surface == "formatting":
        return "low"
    if surface in {"security", "release", "dependency", "runtime"}:
        return "high"
    if surface in {"type_contract", "unknown"}:
        return "medium"
    return "medium"


def _exact_fix_scope(
    *,
    surface: str,
    executable: bool,
    affected_files: list[str],
    strategy: str,
) -> dict[str, Any]:
    if executable:
        return {
            "allowed_files": affected_files,
            "allowed_strategy": strategy,
            "scope": "deterministic formatting or whitespace only",
        }
    return {
        "allowed_files": [],
        "allowed_strategy": strategy,
        "scope": f"review-first {surface}; no automatic mutation",
    }


def plan_from_diagnosis(diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    surface = _string(diagnosis.get(FAILURE_SURFACE)) or "unknown"
    affected_files = _string_list(diagnosis.get(AFFECTED_FILES))
    proof_commands = _string_list(diagnosis.get(PROOF_COMMANDS))
    executable = _is_formatting_executable(diagnosis)
    strategy = (
        _strategy_for_executable_formatting(diagnosis) if executable else _review_strategy(surface)
    )

    commands_to_run = _commands_for_strategy(strategy, proof_commands) if executable else []
    classification = _classification(surface)
    blocked_reason = "" if executable else _blocked_reason(surface, diagnosis)

    return {
        "schema_version": SCHEMA_VERSION,
        DIAGNOSIS_ID: _string(diagnosis.get(DIAGNOSIS_ID)) or "unknown",
        FAILURE_SURFACE: surface,
        CLASSIFICATION: classification,
        CONFIDENCE: _string(diagnosis.get(CONFIDENCE)) or "medium",
        SAFE_TO_AUTO_FIX: executable,
        ALLOWED_STRATEGY: strategy,
        BLOCKED_REASON: blocked_reason,
        AFFECTED_FILES: affected_files,
        EXACT_FIX_SCOPE: _exact_fix_scope(
            surface=surface,
            executable=executable,
            affected_files=affected_files,
            strategy=strategy,
        ),
        COMMANDS_TO_RUN: commands_to_run,
        PROOF_COMMANDS: proof_commands,
        HUMAN_REVIEW_ACTION: _human_review_action(surface, diagnosis),
        ROLLBACK_NOTES: "revert only the remediation commit if proof after fix fails",
        HISTORY_CONTEXT: _string(diagnosis.get(HISTORY_CONTEXT)) or "unknown",
        RISK_LEVEL: _risk_level(surface, executable),
        REQUIRES_FRESH_LOGS: surface in {"unknown", "runtime"},
        REQUIRES_SECURITY_REVIEW: surface == "security",
        REQUIRES_RELEASE_VALIDATION: surface == "release",
    }


def build_remediation_plan(
    diagnostic_vector: Mapping[str, Any],
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    diagnoses = [_as_dict(item) for item in _as_list(diagnostic_vector.get("diagnoses"))]
    plans = [plan_from_diagnosis(diagnosis) for diagnosis in diagnoses if diagnosis]

    executable_count = sum(1 for plan in plans if plan.get(SAFE_TO_AUTO_FIX) is True)
    review_first_count = len(plans) - executable_count
    primary = plans[0] if plans else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "summary": {
            "plan_count": len(plans),
            "executable_plan_count": executable_count,
            "review_first_plan_count": review_first_count,
            "primary_classification": _string(primary.get(CLASSIFICATION)),
            "primary_strategy": _string(primary.get(ALLOWED_STRATEGY)),
            "has_security_review": any(
                plan.get(REQUIRES_SECURITY_REVIEW) is True for plan in plans
            ),
            "has_release_validation": any(
                plan.get(REQUIRES_RELEASE_VALIDATION) is True for plan in plans
            ),
        },
        "plans": plans,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = _as_dict(payload.get("summary"))
    lines = [
        "# Remediation Plan",
        "",
        f"- Plan count: {summary.get('plan_count', 0)}",
        f"- Executable plans: {summary.get('executable_plan_count', 0)}",
        f"- Review-first plans: {summary.get('review_first_plan_count', 0)}",
        f"- Primary classification: {summary.get('primary_classification', '') or 'none'}",
        f"- Primary strategy: {summary.get('primary_strategy', '') or 'none'}",
        "",
        "## Plans",
        "",
    ]

    plans = _as_list(payload.get("plans"))
    if not plans:
        lines.append("- None")
    for item in plans:
        plan = _as_dict(item)
        lines.extend(
            [
                f"### {plan.get(DIAGNOSIS_ID, 'unknown')}",
                "",
                f"- Surface: {plan.get(FAILURE_SURFACE, 'unknown')}",
                f"- Classification: {plan.get(CLASSIFICATION, 'unknown')}",
                f"- Safe to auto-fix: {str(plan.get(SAFE_TO_AUTO_FIX, False)).lower()}",
                f"- Strategy: {plan.get(ALLOWED_STRATEGY, 'unknown')}",
                f"- Blocked reason: {plan.get(BLOCKED_REASON, '')}",
                f"- Risk level: {plan.get(RISK_LEVEL, 'unknown')}",
                f"- Human review action: {plan.get(HUMAN_REVIEW_ACTION, '')}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_remediation_plan(payload: Mapping[str, Any], out_dir: Path) -> dict[str, str]:
    json_path = out_dir / PLAN_JSON
    markdown_path = out_dir / PLAN_MD
    _write_json(json_path, payload)
    _write_text(markdown_path, render_markdown(payload))
    return {
        "remediation_plan_json": json_path.as_posix(),
        "remediation_plan_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.remediation_plan_engine")
    parser.add_argument("--diagnostic-vector", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        diagnostic_vector = _read_json(Path(args.diagnostic_vector))
        payload = build_remediation_plan(
            diagnostic_vector,
            generated_at=args.generated_at,
        )
        artifacts = write_remediation_plan(payload, Path(args.out_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {"artifacts": artifacts, "summary": payload["summary"]}, indent=2, sort_keys=True
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
