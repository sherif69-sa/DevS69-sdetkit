from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.doctor.diagnosis.v1"
ADAPTIVE_FAILURE_BUNDLE_SCHEMA_VERSION = "sdetkit.adaptive.failure_bundle.v1"

_SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_CHECK_CATEGORIES = {
    "ascii": "source_hygiene",
    "ci_workflows": "ci",
    "clean_tree": "release",
    "deps": "dependency",
    "dev_tools": "tooling",
    "pre_commit": "quality",
    "pyproject": "packaging",
    "release_meta": "release",
    "repo_readiness": "repository",
    "security_files": "security",
    "stdlib_shadowing": "code_health",
    "upgrade_audit": "dependency",
    "venv": "environment",
}

_CHECK_COMMANDS = {
    "ascii": "python -m sdetkit doctor --ascii --format json",
    "ci_workflows": "python -m sdetkit doctor --ci --format json",
    "clean_tree": "python -m sdetkit doctor --clean-tree --format json",
    "deps": "python -m sdetkit doctor --deps --format json",
    "pre_commit": "python -m sdetkit doctor --pre-commit --format json",
    "release_meta": "python -m sdetkit doctor --release --format json",
    "repo_readiness": "python -m sdetkit doctor --repo --format json",
    "security_files": "python -m sdetkit doctor --ci --format json",
    "stdlib_shadowing": "python -m sdetkit doctor --format json",
    "upgrade_audit": "python -m sdetkit doctor --upgrade-audit --format json",
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


def _status_from_severity(severity: str) -> str:
    if severity in {"critical", "high"}:
        return "error"
    if severity == "medium":
        return "warning"
    return "info"


def _priority_from_severity(severity: str) -> int:
    priorities = {
        "critical": 95,
        "high": 85,
        "medium": 65,
        "low": 35,
        "info": 20,
    }
    return priorities.get(severity, 50)


def _title_from_check_id(check_id: str) -> str:
    words = check_id.replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else "Doctor finding"


def _payload_confidence(source_doc: dict[str, Any]) -> float:
    judgment = _as_dict(source_doc.get("judgment"))
    confidence = _as_dict(judgment.get("confidence"))
    score = confidence.get("score", 0.75)
    try:
        return round(float(score), 4)
    except (TypeError, ValueError):
        return 0.75


def _payload_status(source_doc: dict[str, Any], diagnoses: Sequence[dict[str, Any]]) -> str:
    judgment = _as_dict(source_doc.get("judgment"))
    status = judgment.get("status")
    if isinstance(status, str) and status and not diagnoses:
        return status

    if not diagnoses:
        return "pass"
    if any(item.get("status") == "error" for item in diagnoses):
        return "fail"
    return "watch"


def _verification_commands(check_id: str) -> list[str]:
    commands = []
    command = _CHECK_COMMANDS.get(check_id)
    if command:
        commands.append(command)
    commands.append("python -m sdetkit gate fast")
    return commands


def _raw_count(check: dict[str, Any], key: str) -> int:
    value = check.get(key)
    return len(value) if isinstance(value, list) else 0


def _safe_evidence(check_id: str, check: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "doctor_check",
            "check_id": check_id,
            "raw_evidence_count": _raw_count(check, "evidence"),
            "raw_fix_count": _raw_count(check, "fix"),
            "note": "Raw doctor evidence is intentionally kept in the source doctor JSON.",
        }
    ]


def _safe_prescriptions(
    check_id: str, check: dict[str, Any], severity: str
) -> list[dict[str, Any]]:
    fix_count = _raw_count(check, "fix")
    if fix_count == 0:
        return []

    return [
        {
            "prescription_id": f"doctor.{check_id}.review_source_fixes",
            "priority": _priority_from_severity(severity),
            "safe_to_auto_apply": False,
            "reason": f"Review the source doctor JSON for {fix_count} suggested fix item(s).",
            "commands": [],
            "verification_commands": _verification_commands(check_id),
        }
    ]


def _diagnosis_from_check(
    check_id: str,
    check: dict[str, Any],
    *,
    confidence: float,
) -> dict[str, Any] | None:
    if bool(check.get("ok", False)):
        return None

    severity = _severity(check.get("severity"))
    summary = f"Doctor check '{check_id}' reported a non-ok result."

    return {
        "diagnosis_id": f"doctor.{check_id}",
        "title": _title_from_check_id(check_id),
        "category": _CHECK_CATEGORIES.get(check_id, "general"),
        "status": _status_from_severity(severity),
        "severity": severity,
        "confidence": confidence,
        "summary": summary,
        "symptoms": [summary],
        "evidence": _safe_evidence(check_id, check),
        "prescriptions": _safe_prescriptions(check_id, check, severity),
        "next_commands": _verification_commands(check_id)[:1],
        "verification_commands": _verification_commands(check_id),
        "source": "doctor",
    }


def _quality_observations(source_doc: dict[str, Any]) -> list[dict[str, Any]]:
    quality = _as_dict(source_doc.get("quality"))
    failed_check_ids = sorted(
        str(check_id) for check_id in _as_list(quality.get("failed_check_ids"))
    )

    return [
        {
            "observation_id": f"doctor.quality.{check_id}",
            "check_id": check_id,
            "summary": f"{_title_from_check_id(check_id)} appears in doctor quality failed_check_ids.",
            "source": "doctor.quality",
        }
        for check_id in failed_check_ids
    ]


def _collect_diagnoses(source_doc: dict[str, Any]) -> list[dict[str, Any]]:
    checks = _as_dict(source_doc.get("checks"))
    confidence = _payload_confidence(source_doc)
    diagnoses = []
    adaptive_bundle_diagnosis = _diagnosis_from_adaptive_failure_bundle(source_doc)
    if adaptive_bundle_diagnosis is not None:
        diagnoses.append(adaptive_bundle_diagnosis)

    for check_id in sorted(checks):
        check = _as_dict(checks[check_id])
        diagnosis = _diagnosis_from_check(check_id, check, confidence=confidence)
        if diagnosis is not None:
            diagnoses.append(diagnosis)

    return diagnoses


def _flatten_prescriptions(diagnoses: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    prescriptions = []
    for diagnosis in diagnoses:
        for prescription in _as_list(diagnosis.get("prescriptions")):
            if isinstance(prescription, dict):
                prescriptions.append(prescription)
    return sorted(
        prescriptions,
        key=lambda item: int(item.get("priority", 0)),
        reverse=True,
    )


def _unique_commands(diagnoses: Sequence[dict[str, Any]], key: str) -> list[str]:
    commands = []
    seen = set()
    for diagnosis in diagnoses:
        for command in _as_list(diagnosis.get(key)):
            command_text = str(command)
            if command_text not in seen:
                seen.add(command_text)
                commands.append(command_text)
    return commands


def _safe_recommendations(
    source_doc: dict[str, Any], diagnoses: Sequence[dict[str, Any]]
) -> list[str]:
    if diagnoses:
        return ["Review diagnosis records and source doctor JSON before remediation."]
    if source_doc.get("ok", True):
        return ["No failed doctor checks were converted into diagnoses."]
    return ["Run doctor with targeted checks to inspect source findings."]


def _diagnosis_from_adaptive_failure_bundle(
    source_doc: dict[str, Any],
) -> dict[str, Any] | None:
    summary = source_doc.get("adaptive_failure_bundle")
    if not isinstance(summary, dict) or not summary.get("enabled"):
        return None

    status = str(summary.get("status", "unknown"))
    primary = str(summary.get("primary_diagnosis_code", "") or "")
    diagnosis_count = int(summary.get("diagnosis_count", 0) or 0)
    review_first = bool(summary.get("review_first", False))
    safe_to_auto_fix = bool(summary.get("safe_to_auto_fix", False))
    has_error = bool(summary.get("error"))

    if (
        not has_error
        and status in {"clear", "monitor"}
        and diagnosis_count == 0
        and not review_first
    ):
        return None

    severity = "high" if review_first or has_error or status == "needs_fix" else "medium"
    primary_display = primary or "none"

    return {
        "diagnosis_id": "doctor.adaptive_failure_bundle",
        "title": "Adaptive failure bundle requires review",
        "category": "adaptive_failure_bundle",
        "status": "fail" if severity == "high" else "warn",
        "severity": severity,
        "confidence": 0.93,
        "summary": (
            f"Adaptive failure bundle status={status}; primary={primary_display}; "
            f"diagnosis_count={diagnosis_count}; review_first={str(review_first).lower()}; "
            f"safe_to_auto_fix={str(safe_to_auto_fix).lower()}."
        ),
        "source": "adaptive_failure_bundle",
        "evidence": [
            f"status={status}",
            f"primary={primary_display}",
            f"diagnosis_count={diagnosis_count}",
            f"review_first={str(review_first).lower()}",
            f"safe_to_auto_fix={str(safe_to_auto_fix).lower()}",
        ],
        "proof_commands": [
            "python -m sdetkit mission-control summarize --bundle build/mission-control/mission-control.json",
        ],
        "prescriptions": [
            {
                "prescription_id": "doctor.adaptive_failure_bundle.review_operator_brief",
                "diagnosis_id": "doctor.adaptive_failure_bundle",
                "action": "review_adaptive_failure_bundle",
                "summary": "Review the adaptive failure bundle operator brief before remediation.",
                "reason": "The adaptive failure bundle is advisory evidence and must remain review-first unless a safe-fix plan is explicitly proven.",
                "severity": severity,
                "priority": 92 if severity == "high" else 70,
                "verification_commands": [
                    "python -m sdetkit mission-control summarize --bundle build/mission-control/mission-control.json",
                ],
            }
        ],
    }


def build_diagnosis_payload(source_doc: dict[str, Any]) -> dict[str, Any]:
    diagnoses = _collect_diagnoses(source_doc)
    observations = _quality_observations(source_doc)
    prescriptions = _flatten_prescriptions(diagnoses)
    severities = [str(diagnosis.get("severity", "low")) for diagnosis in diagnoses]
    severity_counts = Counter(severities)

    judgment = _as_dict(source_doc.get("judgment"))
    top_judgment = _as_dict(judgment.get("top_judgment"))
    source_status = _payload_status(source_doc, diagnoses)
    source_severity = _severity(judgment.get("severity"), fallback="low")
    severity = _max_severity(severities, fallback=source_severity)
    package = _as_dict(source_doc.get("package"))

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(source_doc.get("schema_version", "unknown")),
        "ok": bool(source_doc.get("ok", not diagnoses)) and not diagnoses,
        "status": source_status,
        "severity": severity,
        "confidence": _payload_confidence(source_doc),
        "score": source_doc.get("score", 0),
        "diagnosis_count": len(diagnoses),
        "observation_count": len(observations),
        "prescription_count": len(prescriptions),
        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "info": severity_counts.get("info", 0),
        },
        "diagnoses": diagnoses,
        "observations": observations,
        "prescriptions": prescriptions,
        "next_commands": _unique_commands(diagnoses, "next_commands"),
        "verification_commands": _unique_commands(diagnoses, "verification_commands"),
        "recommendations": _safe_recommendations(source_doc, diagnoses),
        "judgment_next_move": str(top_judgment.get("next_move", "")),
        "source": {
            "workflow": "doctor",
            "package": package.get("name", "unknown"),
            "version": package.get("version", "unknown"),
            "output_path": source_doc.get("output_path", ""),
        },
    }


def load_source_document(path: Path) -> dict[str, Any]:
    raw = sys.stdin.read() if path.as_posix() == "-" else path.read_text(encoding="utf-8")
    source_doc = json.loads(raw)
    if not isinstance(source_doc, dict):
        raise ValueError("doctor payload must be a JSON object")
    return source_doc


def render_text(contract: dict[str, Any]) -> str:
    lines = [
        f"schema_version={contract['schema_version']}",
        f"source_schema_version={contract['source_schema_version']}",
        f"ok={str(contract['ok']).lower()}",
        f"status={contract['status']}",
        f"severity={contract['severity']}",
        f"confidence={contract['confidence']}",
        f"score={contract['score']}",
        f"diagnosis_count={contract['diagnosis_count']}",
        f"observation_count={contract['observation_count']}",
        f"prescription_count={contract['prescription_count']}",
    ]
    for diagnosis in contract["diagnoses"]:
        lines.append(
            "diagnosis={diagnosis_id} status={status} severity={severity} category={category}".format(
                **diagnosis
            )
        )
    return "\n".join(lines)


def _json_contract(contract: dict[str, Any]) -> str:
    return json.dumps(contract, indent=2, sort_keys=True) + "\n"


def _public_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnosis_id": str(diagnosis.get("diagnosis_id", "")),
        "title": str(diagnosis.get("title", "")),
        "category": str(diagnosis.get("category", "general")),
        "status": str(diagnosis.get("status", "info")),
        "severity": str(diagnosis.get("severity", "low")),
        "confidence": diagnosis.get("confidence", 0.0),
        "summary": str(diagnosis.get("summary", "")),
        "source": str(diagnosis.get("source", "doctor")),
    }


def _public_contract_for_output(contract: dict[str, Any]) -> dict[str, Any]:
    source = _as_dict(contract.get("source"))
    severity_counts = _as_dict(contract.get("severity_counts"))

    return {
        "schema_version": str(contract.get("schema_version", SCHEMA_VERSION)),
        "source_schema_version": str(contract.get("source_schema_version", "unknown")),
        "ok": bool(contract.get("ok", False)),
        "status": str(contract.get("status", "unknown")),
        "severity": str(contract.get("severity", "unknown")),
        "confidence": contract.get("confidence", 0.0),
        "score": contract.get("score", 0),
        "diagnosis_count": int(contract.get("diagnosis_count", 0)),
        "observation_count": int(contract.get("observation_count", 0)),
        "prescription_count": int(contract.get("prescription_count", 0)),
        "severity_counts": {
            "critical": int(severity_counts.get("critical", 0)),
            "high": int(severity_counts.get("high", 0)),
            "medium": int(severity_counts.get("medium", 0)),
            "low": int(severity_counts.get("low", 0)),
            "info": int(severity_counts.get("info", 0)),
        },
        "diagnoses": [
            _public_diagnosis(item)
            for item in _as_list(contract.get("diagnoses"))
            if isinstance(item, dict)
        ],
        "observations": [],
        "prescriptions": [],
        "next_commands": [],
        "verification_commands": [],
        "recommendations": [
            "Public-safe diagnosis output written. Review the source doctor JSON for raw evidence."
        ],
        "judgment_next_move": "Review the source doctor JSON for detailed evidence.",
        "source": {
            "workflow": str(source.get("workflow", "doctor")),
            "package": str(source.get("package", "unknown")),
            "version": str(source.get("version", "unknown")),
            "output_path": "[REDACTED]",
        },
    }


def write_output(contract: dict[str, Any], out_path: Path | None, *, output_format: str) -> None:
    public_contract = _public_contract_for_output(contract)
    rendered_contract = (
        _json_contract(public_contract)
        if output_format == "json"
        else render_text(public_contract) + "\n"
    )

    if out_path is None:
        # The CLI emits only the public-safe diagnosis projection built by
        # _public_contract_for_output: raw doctor evidence, raw fix text,
        # command lists, nested prescriptions, and source paths are omitted.
        sys.stdout.write(rendered_contract)  # codeql[py/clear-text-logging-sensitive-data]
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # The file output is the same public-safe projection used for stdout:
    # counts, allowlisted statuses/severities/categories, redacted source
    # metadata, and no raw doctor evidence or fix text.
    out_path.write_text(
        rendered_contract, encoding="utf-8"
    )  # codeql[py/clear-text-storage-sensitive-data]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.doctor_diagnosis",
        description="Convert doctor JSON output into a structured diagnosis contract.",
    )
    parser.add_argument("--source", required=True, help="Path to doctor JSON, or '-' for stdin")
    parser.add_argument("--out", default="", help="Optional output path")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv if argv is not None else sys.argv[1:]))

    try:
        source_doc = load_source_document(Path(args.source))
        contract = build_diagnosis_payload(source_doc)
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
