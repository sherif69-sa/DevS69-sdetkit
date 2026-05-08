from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.learning_import.v1"
SUPPORTED_EXPORT_SCHEMA = "sdetkit.adaptive.enterprise_learning_export.v1"
REDACTED = "<redacted>"
PRIVATE_KEYS = {
    "repo",
    "repository",
    "source_path",
    "note",
    "changed_file_scope",
    "affected_files",
    "files",
    "url",
    "issue_url",
    "hostname",
    "host",
    "user",
    "username",
}
PATH_PATTERN = re.compile(r"(^|[\s=:/\\])([A-Za-z]:)?([./~]?[^\s|,;:]+[\\/][^\s|,;:]+)")
FILE_PATTERN = re.compile(r"\b[\w.-]+\.(py|toml|yaml|yml|json|md|txt|log|ini|cfg)\b")
URL_PATTERN = re.compile(r"https?://[^\s]+")
HOSTNAME_PATTERN = re.compile(
    r"\b(?!(?:sdetkit|adaptive|enterprise|learning|export|schema|version)\b)"
    r"[a-zA-Z0-9][a-zA-Z0-9-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9-]*)+\b"
)
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object at line {line_number}")
        records.append(payload)
    return records


def _records_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") == SUPPORTED_EXPORT_SCHEMA:
        return [_as_dict(row) for row in _as_list(payload.get("records")) if isinstance(row, dict)]
    if "records" in payload:
        return [_as_dict(row) for row in _as_list(payload.get("records")) if isinstance(row, dict)]
    return [payload]


def _is_redacted_value(value: Any) -> bool:
    if value == REDACTED:
        return True
    if isinstance(value, list):
        return all(item == REDACTED for item in value)
    return False


def _private_identifier_code(value: str) -> str | None:
    if URL_PATTERN.search(value):
        return "PRIVATE_URL_PATTERN"
    if EMAIL_PATTERN.search(value):
        return "PRIVATE_EMAIL_PATTERN"
    if PATH_PATTERN.search(value) or FILE_PATTERN.search(value):
        return "PRIVATE_IDENTIFIER_PATTERN"
    if HOSTNAME_PATTERN.search(value):
        return "PRIVATE_HOSTNAME_PATTERN"
    return None


def _redaction_findings(value: Any, path: str = "$") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in PRIVATE_KEYS and not _is_redacted_value(item):
                findings.append(
                    {
                        "code": "PRIVATE_FIELD_NOT_REDACTED",
                        "severity": "critical",
                        "path": child_path,
                        "message": f"Private field {key} must be {REDACTED} before import.",
                    }
                )
            findings.extend(_redaction_findings(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_redaction_findings(item, f"{path}[{index}]"))
    elif isinstance(value, str) and value != REDACTED:
        code = _private_identifier_code(value)
        if code is not None:
            findings.append(
                {
                    "code": code,
                    "severity": "critical",
                    "path": path,
                    "message": (
                        "String looks like a private path, URL, hostname, email, or file "
                        "identifier and cannot be imported."
                    ),
                    "evidence": _safe_text(value, 120),
                }
            )
    return findings


def _scenario_code(row: dict[str, Any]) -> str:
    for key in ("source_code", "code", "scenario_code"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "UNKNOWN"


def _calibration_hints(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "records": 0,
            "proof_passed_count": 0,
            "proof_failed_count": 0,
            "false_positive_count": 0,
            "fix_accepted_count": 0,
            "outcomes": Counter(),
        }
    )
    for row in records:
        code = _scenario_code(row)
        group = groups[code]
        group["records"] += 1
        outcome = str(row.get("outcome", "unknown"))
        group["outcomes"][outcome] += 1
        if outcome == "proof_passed" or bool(row.get("proof_passed")):
            group["proof_passed_count"] += 1
        if outcome == "proof_failed" or bool(row.get("proof_failed")):
            group["proof_failed_count"] += 1
        if bool(row.get("false_positive")):
            group["false_positive_count"] += 1
        if bool(row.get("fix_accepted")):
            group["fix_accepted_count"] += 1
    hints: list[dict[str, Any]] = []
    for code, group in sorted(groups.items()):
        action = "observe"
        confidence_delta = 0
        risk_delta = 0
        if group["false_positive_count"]:
            action = "demote"
            confidence_delta = -2
            risk_delta = -10
        elif group["proof_failed_count"]:
            action = "review_guardrail"
            confidence_delta = -1
            risk_delta = 8
        elif group["proof_passed_count"] or group["fix_accepted_count"]:
            action = "promote"
            confidence_delta = 1
            risk_delta = 4
        hints.append(
            {
                "scenario_code": code,
                "records": group["records"],
                "action": action,
                "confidence_delta": confidence_delta,
                "risk_delta": risk_delta,
                "proof_passed_count": group["proof_passed_count"],
                "proof_failed_count": group["proof_failed_count"],
                "false_positive_count": group["false_positive_count"],
                "fix_accepted_count": group["fix_accepted_count"],
                "outcomes": dict(sorted(group["outcomes"].items())),
            }
        )
    return hints


def build_learning_import(payload: dict[str, Any]) -> dict[str, Any]:
    records = _records_from_payload(payload)
    findings: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        findings.extend(_redaction_findings(record, f"$.records[{index}]"))
    hints = [] if findings else _calibration_hints(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not findings,
        "recommendation": "IMPORT" if not findings else "REJECT_IMPORT",
        "record_count": len(records),
        "finding_count": len(findings),
        "findings": findings[:20],
        "calibration_hints": hints,
        "calibration_hint_count": len(hints),
        "privacy_controls": {
            "required_placeholder": REDACTED,
            "private_keys": sorted(PRIVATE_KEYS),
            "raw_path_detection": True,
            "url_hostname_email_detection": True,
        },
        "next_owner_action": "Import calibration hints into local adaptive review only."
        if not findings
        else "Reject import and re-run anonymized export/redaction before sharing learning.",
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"recommendation={payload['recommendation']}",
        f"record_count={payload['record_count']}",
        f"finding_count={payload['finding_count']}",
        f"calibration_hint_count={payload['calibration_hint_count']}",
    ]
    for row in _as_list(payload.get("calibration_hints"))[:8]:
        item = _as_dict(row)
        lines.append(
            f"hint={item.get('scenario_code')}|action={item.get('action')}|records={item.get('records')}"
        )
    for row in _as_list(payload.get("findings"))[:8]:
        item = _as_dict(row)
        lines.append(f"finding={item.get('code')}|{item.get('path')}|{item.get('message')}")
    lines.append(f"next_owner_action={payload['next_owner_action']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_learning_import")
    parser.add_argument("learning_export", help="Anonymized learning JSON export or JSONL records")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = Path(args.learning_export)
        if path.suffix.lower() == ".jsonl":
            payload = {"records": _load_jsonl(path)}
        else:
            payload = _load_json(path)
        result = build_learning_import(payload)
        rendered = (
            json.dumps(result, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_text(result)
        )
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
