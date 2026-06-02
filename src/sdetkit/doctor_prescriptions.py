from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.doctor.prescriptions.v1"

_SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_PRIORITY_BY_SEVERITY = {
    "critical": 95,
    "high": 85,
    "medium": 65,
    "low": 35,
    "info": 20,
}

_CHECK_GUIDANCE = {
    "adaptive_failure_bundle": {
        "action": "review_adaptive_failure_bundle",
        "summary": "Review the adaptive failure bundle and operator brief before remediation.",
        "why": "Adaptive failure bundle signals are diagnostic handoff evidence, not permission to auto-fix.",
        "category": "adaptive_failure_bundle",
        "verification_commands": [
            "python -m sdetkit mission-control summarize --bundle build/mission-control/mission-control.json",
        ],
    },
    "ascii": {
        "category": "source_hygiene",
        "action": "rerun_ascii_doctor_check",
        "summary": "Inspect ASCII hygiene findings before release.",
        "why": "Non-ASCII surprises can make logs, docs, and generated artifacts harder to review.",
        "verification_commands": [
            "python -m sdetkit doctor --ascii --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "ci_workflows": {
        "category": "ci",
        "action": "repair_ci_workflow_signal",
        "summary": "Repair CI workflow signal before relying on release gates.",
        "why": "Release confidence depends on predictable CI lint, test, and quality checks.",
        "verification_commands": [
            "python -m sdetkit doctor --ci --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "clean_tree": {
        "category": "release",
        "action": "resolve_dirty_worktree",
        "summary": "Commit, stash, or intentionally remove local changes before release.",
        "why": "Release checks need a clean tree so the verified artifact matches the submitted state.",
        "verification_commands": [
            "python -m sdetkit doctor --clean-tree --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "deps": {
        "category": "dependency",
        "action": "restore_dependency_consistency",
        "summary": "Align dependency metadata and test requirements.",
        "why": "Dependency drift can make local, CI, and release checks disagree.",
        "verification_commands": [
            "python -m sdetkit doctor --deps --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "dev_tools": {
        "category": "tooling",
        "action": "restore_developer_tooling",
        "summary": "Restore expected developer tooling for local verification.",
        "why": "Missing local tools make repair loops slower and less reproducible.",
        "verification_commands": [
            "python -m sdetkit doctor --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "pre_commit": {
        "category": "quality",
        "action": "run_pre_commit_repairs",
        "summary": "Run pre-commit hooks and commit their resulting changes.",
        "why": "Pre-commit hooks enforce formatting, whitespace, typing, and repository hygiene before CI.",
        "verification_commands": [
            "python -m pre_commit run -a",
            "python -m sdetkit gate fast",
        ],
    },
    "pyproject": {
        "category": "packaging",
        "action": "repair_project_metadata",
        "summary": "Repair project metadata before release validation.",
        "why": "Packaging metadata drives build, install, and publishing behavior.",
        "verification_commands": [
            "python -m sdetkit doctor --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "release_meta": {
        "category": "release",
        "action": "repair_release_metadata",
        "summary": "Repair release metadata before shipping.",
        "why": "Release metadata keeps published versions, changelogs, and release evidence aligned.",
        "verification_commands": [
            "python -m sdetkit doctor --release --format json",
            "python -m sdetkit gate release",
        ],
    },
    "repo_readiness": {
        "category": "repository",
        "action": "repair_repo_readiness_gap",
        "summary": "Address the repository readiness gap reported by doctor.",
        "why": "Readiness checks protect the basic repository controls expected by operators.",
        "verification_commands": [
            "python -m sdetkit readiness",
            "python -m sdetkit gate fast",
        ],
    },
    "security_files": {
        "category": "security",
        "action": "repair_security_governance_files",
        "summary": "Repair security governance files before release.",
        "why": "Security policy and governance files make vulnerability handling explicit.",
        "verification_commands": [
            "python -m sdetkit doctor --ci --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "stdlib_shadowing": {
        "category": "code_health",
        "action": "remove_stdlib_" + "shadowing",
        "summary": "Rename files or packages that shadow Python standard-library modules.",
        "why": "Stdlib shadowing can create confusing import behavior across machines and CI.",
        "verification_commands": [
            "python -m sdetkit doctor --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "upgrade_audit": {
        "category": "dependency",
        "action": "review_upgrade_audit",
        "summary": "Review dependency upgrade audit findings.",
        "why": "Upgrade audit findings can expose dependency compatibility or release risk.",
        "verification_commands": [
            "python -m sdetkit doctor --upgrade-audit --format json",
            "python -m sdetkit gate fast",
        ],
    },
    "venv": {
        "category": "environment",
        "action": "restore_virtual_environment",
        "summary": "Recreate or reactivate the expected local virtual environment.",
        "why": "A healthy environment is required for repeatable local verification.",
        "verification_commands": [
            "python -m sdetkit doctor --format json",
            "python -m sdetkit gate fast",
        ],
    },
}

_GENERIC_GUIDANCE = {
    "category": "general",
    "action": "review_doctor_diagnosis",
    "summary": "Review the doctor diagnosis and choose a targeted repair.",
    "why": "The diagnosis did not match a known prescription template yet.",
    "verification_commands": [
        "python -m sdetkit doctor --format json",
        "python -m sdetkit gate fast",
    ],
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _severity(value: Any, *, fallback: str = "medium") -> str:
    candidate = str(value or fallback).lower()
    return candidate if candidate in _SEVERITY_RANK else fallback


def _max_severity(severities: Sequence[str], *, fallback: str = "low") -> str:
    if not severities:
        return fallback
    return max(severities, key=lambda item: _SEVERITY_RANK.get(item, 0))


def _priority(severity: str) -> int:
    return _PRIORITY_BY_SEVERITY.get(severity, 50)


def _diagnosis_check_id(diagnosis: dict[str, Any]) -> str:
    raw_id = str(diagnosis.get("diagnosis_id", ""))
    if not raw_id.startswith("doctor."):
        return "unknown"
    check_id = raw_id.split(".", 1)[1]
    return check_id if check_id in _CHECK_GUIDANCE else "unknown"


def _safe_category(value: Any, fallback: str) -> str:
    candidate = str(value or fallback).lower()
    allowed = {
        "ci",
        "code_health",
        "dependency",
        "environment",
        "general",
        "packaging",
        "quality",
        "release",
        "repository",
        "security",
        "source_hygiene",
        "tooling",
    }
    return candidate if candidate in allowed else fallback


def _public_output_status(value: Any) -> str:
    candidate = str(value or "unknown").lower()
    allowed = {"action_required", "pass", "unknown"}
    return candidate if candidate in allowed else "unknown"


def _public_output_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return fallback


def _public_output_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _guidance_for(check_id: str) -> dict[str, Any]:
    return _CHECK_GUIDANCE.get(check_id, _GENERIC_GUIDANCE)


def _prescription_from_diagnosis(index: int, diagnosis: dict[str, Any]) -> dict[str, Any]:
    check_id = _diagnosis_check_id(diagnosis)
    guidance = _guidance_for(check_id)
    severity = _severity(diagnosis.get("severity"))
    category = _safe_category(diagnosis.get("category"), str(guidance.get("category", "general")))
    action = str(guidance.get("action", "review_doctor_diagnosis"))
    diagnosis_id = f"doctor.{check_id}" if check_id != "unknown" else "doctor.unknown"

    return {
        "prescription_id": f"{diagnosis_id}.{action}.{index}",
        "diagnosis_id": diagnosis_id,
        "category": category,
        "severity": severity,
        "priority": _priority(severity),
        "safe_to_auto_apply": False,
        "summary": str(guidance.get("summary", _GENERIC_GUIDANCE["summary"])),
        "why": str(guidance.get("why", _GENERIC_GUIDANCE["why"])),
        "commands": [],
        "verification_commands": [
            str(command) for command in _as_list(guidance.get("verification_commands"))
        ],
        "source": "doctor_prescriptions",
    }


def _collect_prescriptions(source_doc: dict[str, Any]) -> list[dict[str, Any]]:
    prescriptions = []
    for index, item in enumerate(_as_list(source_doc.get("diagnoses")), start=1):
        if isinstance(item, dict):
            prescriptions.append(_prescription_from_diagnosis(index, item))

    return sorted(
        prescriptions,
        key=lambda item: (int(item.get("priority", 0)), str(item.get("prescription_id", ""))),
        reverse=True,
    )


def _unique_commands(prescriptions: Sequence[dict[str, Any]]) -> list[str]:
    seen = set()
    commands = []
    for prescription in prescriptions:
        for command in _as_list(prescription.get("verification_commands")):
            command_text = str(command)
            if command_text not in seen:
                seen.add(command_text)
                commands.append(command_text)
    return commands


def build_prescription_payload(source_doc: dict[str, Any]) -> dict[str, Any]:
    prescriptions = _collect_prescriptions(source_doc)
    severities = [str(prescription.get("severity", "low")) for prescription in prescriptions]
    severity_counts = Counter(severities)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(source_doc.get("schema_version", "unknown")),
        "ok": len(prescriptions) == 0,
        "status": "pass" if not prescriptions else "action_required",
        "severity": _max_severity(severities, fallback="low"),
        "confidence": source_doc.get("confidence", 0.0),
        "prescription_count": len(prescriptions),
        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "info": severity_counts.get("info", 0),
        },
        "prescriptions": prescriptions,
        "next_commands": _unique_commands(prescriptions)[:3],
        "verification_commands": _unique_commands(prescriptions),
        "source": {
            "workflow": "doctor_diagnosis",
            "source_output_path": "[REDACTED]",
        },
    }


def load_source_document(path: Path) -> dict[str, Any]:
    raw = sys.stdin.read() if path.as_posix() == "-" else path.read_text(encoding="utf-8")
    source_doc = json.loads(raw)
    if not isinstance(source_doc, dict):
        raise ValueError("doctor diagnosis payload must be a JSON object")
    return source_doc


def render_text(contract: dict[str, Any]) -> str:
    lines = [
        f"schema_version={contract['schema_version']}",
        f"source_schema_version={contract['source_schema_version']}",
        f"ok={str(contract['ok']).lower()}",
        f"status={contract['status']}",
        f"severity={contract['severity']}",
        f"confidence={contract['confidence']}",
        f"prescription_count={contract['prescription_count']}",
    ]
    return "\n".join(lines)


def _json_contract(contract: dict[str, Any]) -> str:
    return json.dumps(contract, indent=2, sort_keys=True) + "\n"


def _public_output_contract(contract: dict[str, Any]) -> dict[str, Any]:
    severity_counts = _as_dict(contract.get("severity_counts"))

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": "sdetkit.doctor.diagnosis.v1",
        "ok": bool(contract.get("ok", False)),
        "status": _public_output_status(contract.get("status")),
        "severity": _severity(contract.get("severity"), fallback="low"),
        "confidence": _public_output_float(contract.get("confidence")),
        "prescription_count": _public_output_int(contract.get("prescription_count")),
        "severity_counts": {
            "critical": _public_output_int(severity_counts.get("critical")),
            "high": _public_output_int(severity_counts.get("high")),
            "medium": _public_output_int(severity_counts.get("medium")),
            "low": _public_output_int(severity_counts.get("low")),
            "info": _public_output_int(severity_counts.get("info")),
        },
        "prescriptions": [],
        "next_commands": [],
        "verification_commands": [],
        "source": {
            "workflow": "doctor_prescriptions",
            "source_output_path": "[REDACTED]",
        },
    }


def write_output(contract: dict[str, Any], out_path: Path | None, *, output_format: str) -> None:
    public_contract = _public_output_contract(contract)
    if output_format == "json":
        rendered_contract = _json_contract(public_contract)
    else:
        rendered_contract = render_text(public_contract) + "\n"

    if out_path is None:
        sys.stdout.write(rendered_contract)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered_contract, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.doctor_prescriptions",
        description="Convert doctor diagnosis JSON into public-safe prescription guidance.",
    )
    parser.add_argument(
        "--source", required=True, help="Path to doctor diagnosis JSON, or '-' for stdin"
    )
    parser.add_argument("--out", default="", help="Optional output path")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv if argv is not None else sys.argv[1:]))

    try:
        source_doc = load_source_document(Path(args.source))
        contract = build_prescription_payload(source_doc)
        write_output(
            contract,
            Path(args.out) if args.out else None,
            output_format=args.format,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
