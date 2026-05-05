from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sdetkit import github_actions_annotation_hygiene

SCHEMA_VERSION = "sdetkit.github_actions.annotation_hygiene_report.v1"
CHECK_NAME = "github_actions_annotation_hygiene"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _annotation_payload_from_maintenance_report(report: dict[str, Any]) -> dict[str, Any]:
    checks = _as_dict(report.get("checks"))
    check = _as_dict(checks.get(CHECK_NAME))
    details = _as_dict(check.get("details"))
    payload = _as_dict(details.get("annotation_hygiene"))
    if payload:
        return payload
    return {
        "schema_version": github_actions_annotation_hygiene.SCHEMA_VERSION,
        "ok": True,
        "finding_count": 0,
        "warning_count": 0,
        "notice_count": 0,
        "findings": [],
    }


def build_report(
    annotation_payload: dict[str, Any],
    *,
    source_type: str,
    source_path: str = "",
) -> dict[str, Any]:
    findings = [
        item for item in _as_list(annotation_payload.get("findings")) if isinstance(item, dict)
    ]
    by_severity: dict[str, int] = {}
    by_id: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity", "unknown"))
        finding_id = str(finding.get("id", "unknown"))
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_id[finding_id] = by_id.get(finding_id, 0) + 1

    warning_count = _int_value(annotation_payload.get("warning_count"))
    notice_count = _int_value(annotation_payload.get("notice_count"))
    finding_count = _int_value(annotation_payload.get("finding_count", len(findings)))
    top_actions = []
    for finding in findings[:5]:
        recommendation = str(finding.get("recommendation", "")).strip()
        title = str(finding.get("title", "")).strip()
        if recommendation:
            top_actions.append(recommendation)
        elif title:
            top_actions.append(title)

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": warning_count == 0,
        "source_type": source_type,
        "source_path": source_path,
        "finding_count": finding_count,
        "warning_count": warning_count,
        "notice_count": notice_count,
        "by_severity": dict(sorted(by_severity.items())),
        "by_id": dict(sorted(by_id.items())),
        "top_actions": list(dict.fromkeys(top_actions)),
        "annotation_hygiene": annotation_payload,
    }


def report_from_maintenance_json(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"expected maintenance JSON object in {path}")
    return build_report(
        _annotation_payload_from_maintenance_report(report),
        source_type="maintenance_json",
        source_path=path.as_posix(),
    )


def report_from_annotation_log(path: Path) -> dict[str, Any]:
    return build_report(
        github_actions_annotation_hygiene.analyze_file(path),
        source_type="annotation_log",
        source_path=path.as_posix(),
    )


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitHub Actions annotation hygiene report",
        "",
        f"- source: `{report.get('source_type', 'unknown')}`",
        f"- findings: **{report.get('finding_count', 0)}**",
        f"- warnings: **{report.get('warning_count', 0)}**",
        f"- notices: **{report.get('notice_count', 0)}**",
    ]

    by_id = _as_dict(report.get("by_id"))
    if by_id:
        lines.extend(["", "## Finding types", ""])
        for finding_id, count in by_id.items():
            lines.append(f"- `{finding_id}`: {count}")

    findings = _as_list(_as_dict(report.get("annotation_hygiene")).get("findings"))
    if findings:
        lines.extend(["", "## Findings", ""])
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.extend(
                [
                    f"### {finding.get('title', 'Finding')}",
                    "",
                    f"- id: `{finding.get('id', 'unknown')}`",
                    f"- severity: `{finding.get('severity', 'unknown')}`",
                    f"- job: `{finding.get('job', 'unknown')}`",
                ]
            )
            action = str(finding.get("action", "")).strip()
            if action:
                lines.append(f"- action: `{action}`")
            lines.extend(
                [
                    f"- evidence: {finding.get('evidence', '')}",
                    f"- recommendation: {finding.get('recommendation', '')}",
                    "",
                ]
            )
    else:
        lines.extend(["", "No GitHub Actions annotation hygiene findings detected."])

    top_actions = _as_list(report.get("top_actions"))
    if top_actions:
        lines.extend(["", "## Suggested next actions", ""])
        for action in top_actions:
            lines.append(f"- {action}")

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.github_actions_annotation_hygiene_report"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--maintenance-json")
    source.add_argument("--annotation-log")
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.maintenance_json:
            report = report_from_maintenance_json(Path(args.maintenance_json))
        else:
            report = report_from_annotation_log(Path(args.annotation_log))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(report)

    if args.out_json:
        Path(args.out_json).write_text(json_text, encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    if args.format == "json":
        print(json_text, end="")
    else:
        print(md_text, end="")

    return 1 if report.get("warning_count", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
