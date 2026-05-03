from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.doctor.diagnosis.v1"

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


def _as_string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]


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


def _payload_confidence(payload: dict[str, Any]) -> float:
    judgment = _as_dict(payload.get("judgment"))
    confidence = _as_dict(judgment.get("confidence"))
    score = confidence.get("score", 0.75)
    try:
        return round(float(score), 4)
    except (TypeError, ValueError):
        return 0.75


def _payload_status(payload: dict[str, Any], diagnoses: Sequence[dict[str, Any]]) -> str:
    judgment = _as_dict(payload.get("judgment"))
    status = judgment.get("status")
    if isinstance(status, str) and status:
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


def _diagnosis_from_check(
    check_id: str,
    check: dict[str, Any],
    *,
    confidence: float,
) -> dict[str, Any] | None:
    if bool(check.get("ok", False)):
        return None

    severity = _severity(check.get("severity"))
    summary = str(check.get("summary") or f"{_title_from_check_id(check_id)} failed.")
    evidence = _as_string_list(check.get("evidence"))
    fixes = _as_string_list(check.get("fix"))
    prescriptions = [
        {
            "prescription_id": f"doctor.{check_id}.fix_{index}",
            "priority": _priority_from_severity(severity),
            "safe_to_auto_apply": False,
            "reason": fix,
            "commands": [],
            "verification_commands": _verification_commands(check_id),
        }
        for index, fix in enumerate(fixes, start=1)
    ]

    return {
        "diagnosis_id": f"doctor.{check_id}",
        "title": _title_from_check_id(check_id),
        "category": _CHECK_CATEGORIES.get(check_id, "general"),
        "status": _status_from_severity(severity),
        "severity": severity,
        "confidence": confidence,
        "summary": summary,
        "symptoms": [summary],
        "evidence": evidence,
        "prescriptions": prescriptions,
        "next_commands": _verification_commands(check_id)[:1],
        "verification_commands": _verification_commands(check_id),
        "source": "doctor",
    }


def _missing_check_diagnoses(
    payload: dict[str, Any],
    known_check_ids: set[str],
    *,
    confidence: float,
) -> list[dict[str, Any]]:
    quality = _as_dict(payload.get("quality"))
    failed_check_ids = sorted(
        str(check_id)
        for check_id in _as_list(quality.get("failed_check_ids"))
        if str(check_id) not in known_check_ids
    )

    diagnoses = []
    for check_id in failed_check_ids:
        severity = _severity(
            _as_dict(quality.get("failed_severity_breakdown")).get(check_id),
            fallback="medium",
        )
        summary = f"{_title_from_check_id(check_id)} is reported as failed by doctor quality data."
        diagnoses.append(
            {
                "diagnosis_id": f"doctor.{check_id}",
                "title": _title_from_check_id(check_id),
                "category": _CHECK_CATEGORIES.get(check_id, "general"),
                "status": _status_from_severity(severity),
                "severity": severity,
                "confidence": confidence,
                "summary": summary,
                "symptoms": [summary],
                "evidence": [],
                "prescriptions": [],
                "next_commands": ["python -m sdetkit doctor --format json"],
                "verification_commands": [
                    "python -m sdetkit doctor --format json",
                    "python -m sdetkit gate fast",
                ],
                "source": "doctor.quality",
            }
        )
    return diagnoses


def _collect_diagnoses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    checks = _as_dict(payload.get("checks"))
    confidence = _payload_confidence(payload)
    diagnoses = []

    for check_id in sorted(checks):
        check = _as_dict(checks[check_id])
        diagnosis = _diagnosis_from_check(check_id, check, confidence=confidence)
        if diagnosis is not None:
            diagnoses.append(diagnosis)

    diagnoses.extend(_missing_check_diagnoses(payload, set(checks), confidence=confidence))
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
        for command in _as_string_list(diagnosis.get(key)):
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return commands


def build_diagnosis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    diagnoses = _collect_diagnoses(payload)
    prescriptions = _flatten_prescriptions(diagnoses)
    severities = [str(diagnosis.get("severity", "low")) for diagnosis in diagnoses]
    severity_counts = Counter(severities)

    status = _payload_status(payload, diagnoses)
    severity = _max_severity(
        severities,
        fallback=_severity(_as_dict(payload.get("judgment")).get("severity"), fallback="low"),
    )

    package = _as_dict(payload.get("package"))
    judgment = _as_dict(payload.get("judgment"))
    top_judgment = _as_dict(judgment.get("top_judgment"))

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": str(payload.get("schema_version", "unknown")),
        "ok": bool(payload.get("ok", not diagnoses)) and not diagnoses,
        "status": status,
        "severity": severity,
        "confidence": _payload_confidence(payload),
        "score": payload.get("score", 0),
        "diagnosis_count": len(diagnoses),
        "prescription_count": len(prescriptions),
        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "info": severity_counts.get("info", 0),
        },
        "diagnoses": diagnoses,
        "prescriptions": prescriptions,
        "next_commands": _unique_commands(diagnoses, "next_commands"),
        "verification_commands": _unique_commands(diagnoses, "verification_commands"),
        "recommendations": _as_string_list(payload.get("recommendations")),
        "judgment_next_move": top_judgment.get("next_move", ""),
        "source": {
            "workflow": "doctor",
            "package": package.get("name", "unknown"),
            "version": package.get("version", "unknown"),
            "output_path": payload.get("output_path", ""),
        },
    }


def load_payload(path: Path) -> dict[str, Any]:
    if path.as_posix() == "-":
        raw = sys.stdin.read()
    else:
        raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("doctor payload must be a JSON object")
    return payload


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"source_schema_version={payload['source_schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"status={payload['status']}",
        f"severity={payload['severity']}",
        f"confidence={payload['confidence']}",
        f"score={payload['score']}",
        f"diagnosis_count={payload['diagnosis_count']}",
        f"prescription_count={payload['prescription_count']}",
    ]
    for diagnosis in payload["diagnoses"]:
        lines.append(
            "diagnosis={diagnosis_id} status={status} severity={severity} category={category}".format(
                **diagnosis
            )
        )
    return "\n".join(lines)


def write_output(payload: dict[str, Any], out_path: Path | None, *, output_format: str) -> None:
    if output_format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_text(payload) + "\n"

    if out_path is None:
        print(rendered, end="")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")


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
        source_payload = load_payload(Path(args.source))
        diagnosis_payload = build_diagnosis_payload(source_payload)
        write_output(
            diagnosis_payload,
            Path(args.out) if args.out else None,
            output_format=args.format,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
