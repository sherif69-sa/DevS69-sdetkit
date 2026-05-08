from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sdetkit import adaptive_diagnosis

SCHEMA_VERSION = "sdetkit.adaptive.enterprise_governance.v1"
EXPORT_SCHEMA_VERSION = "sdetkit.adaptive.enterprise_learning_export.v1"
SENSITIVE_TAGS = {"security-sensitive", "secret-sensitive", "private-sensitive"}
ISOLATION_TAG = "security-isolated"
APPROVAL_TAG = adaptive_diagnosis.APPROVED_OVERRIDE_TAG
REDACTED = "<redacted>"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _scenario_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer in _as_list(report.get("layers")):
        item = _as_dict(layer)
        source = str(item.get("source", "unknown"))
        path = Path(str(item.get("path", "")))
        if not path.exists():
            continue
        for scenario in adaptive_diagnosis.load_scenario_pack(path):
            rows.append(
                {
                    "code": scenario.code,
                    "source": source,
                    "tags": list(scenario.tags),
                    "risk_band": scenario.risk_band,
                }
            )
    return rows


def _violation(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "message": message, **extra}


def build_governance_report(root: Path | None = None) -> dict[str, Any]:
    pack_report = adaptive_diagnosis.layered_scenario_pack_report(root)
    scenario_rows = _scenario_rows(pack_report)
    violations: list[dict[str, Any]] = []
    for override in _as_list(pack_report.get("overrides")):
        item = _as_dict(override)
        if not bool(item.get("approved")):
            violations.append(
                _violation(
                    "unapproved_override",
                    f"Scenario {item.get('code')} override requires {APPROVAL_TAG}.",
                    code=item.get("code"),
                    source=item.get("source"),
                )
            )
    sensitive_rows: list[dict[str, Any]] = []
    for row in scenario_rows:
        tags = {str(tag) for tag in _as_list(row.get("tags"))}
        if not tags.intersection(SENSITIVE_TAGS):
            continue
        sensitive_rows.append(row)
        if ISOLATION_TAG not in tags:
            violations.append(
                _violation(
                    "sensitive_scenario_not_isolated",
                    f"Scenario {row.get('code')} is sensitive but missing {ISOLATION_TAG}.",
                    code=row.get("code"),
                    source=row.get("source"),
                )
            )
    recommendation = "APPROVED" if not violations else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not violations,
        "recommendation": recommendation,
        "next_owner_action": "Governance controls passed; pack overlays may be used."
        if not violations
        else "Resolve pack approval or sensitive-scenario isolation violations before rollout.",
        "pack_report_schema_version": pack_report.get("schema_version"),
        "layer_count": pack_report.get("layer_count", 0),
        "scenario_count": pack_report.get("scenario_count", 0),
        "override_count": len(_as_list(pack_report.get("overrides"))),
        "sensitive_scenario_count": len(sensitive_rows),
        "violations": violations,
        "controls": {
            "override_approval_tag": APPROVAL_TAG,
            "sensitive_tags": sorted(SENSITIVE_TAGS),
            "isolation_tag": ISOLATION_TAG,
            "anonymized_learning_export": True,
        },
    }


def anonymize_record(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in record.items():
        if key in {"repo", "repository", "source_path", "note", "changed_file_scope"}:
            out[key] = REDACTED if not isinstance(value, list) else [REDACTED for _ in value]
        elif key in {"affected_files", "files"}:
            out[key] = [REDACTED for _ in _as_list(value)]
        elif isinstance(value, dict):
            out[key] = anonymize_record(value)
        elif isinstance(value, list):
            out[key] = [
                anonymize_record(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            out[key] = value
    return out


def build_anonymized_learning_export(records: list[dict[str, Any]]) -> dict[str, Any]:
    anonymized = [anonymize_record(record) for record in records]
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "ok": True,
        "record_count": len(anonymized),
        "redaction_policy": {
            "redacted_fields": [
                "repo",
                "repository",
                "source_path",
                "note",
                "changed_file_scope",
                "affected_files",
                "files",
            ],
            "placeholder": REDACTED,
        },
        "records": anonymized,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_enterprise_governance")
    sub = parser.add_subparsers(dest="cmd", required=True)
    report = sub.add_parser("report", help="Build adaptive enterprise governance report")
    report.add_argument("--root", default=".")
    report.add_argument("--format", choices=["text", "json"], default="text")
    report.add_argument("--out", default="")
    export = sub.add_parser(
        "anonymize-learning", help="Anonymize adaptive JSONL records for export"
    )
    export.add_argument("jsonl_path")
    export.add_argument("--format", choices=["text", "json"], default="json")
    export.add_argument("--out", default="")
    return parser


def _render_text(payload: dict[str, Any]) -> str:
    if payload.get("schema_version") == EXPORT_SCHEMA_VERSION:
        return (
            f"schema_version={payload['schema_version']}\n"
            f"ok={str(payload['ok']).lower()}\n"
            f"record_count={payload['record_count']}\n"
        )
    return (
        f"schema_version={payload['schema_version']}\n"
        f"ok={str(payload['ok']).lower()}\n"
        f"recommendation={payload['recommendation']}\n"
        f"violation_count={len(_as_list(payload.get('violations')))}\n"
        f"next_owner_action={payload['next_owner_action']}\n"
    )


def _write_or_print(rendered: str, out: str) -> None:
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "report":
            payload = build_governance_report(Path(args.root))
        else:
            payload = build_anonymized_learning_export(_load_jsonl(Path(args.jsonl_path)))
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else _render_text(payload)
        )
        _write_or_print(rendered, str(args.out))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
