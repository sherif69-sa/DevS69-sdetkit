from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.github_actions.annotation_hygiene.v1"

_NODE20_ACTION_RE = re.compile(
    r"(?P<action>[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+@[A-Za-z0-9_.:/-]+)"
)
_JOB_RE = re.compile(r"^(?P<job>[A-Za-z0-9_. -]+)$")


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


def _nearest_job(lines: list[str], index: int) -> str:
    for pos in range(index, -1, -1):
        candidate = lines[pos].strip()
        if not candidate:
            continue
        if candidate.startswith(("Warning:", "Notice:", "Error:", "Run ", "with:", "env:")):
            continue
        if candidate.startswith(("-", "{", "}", '"')):
            continue
        match = _JOB_RE.match(candidate)
        if match:
            return match.group("job").strip()
    return "unknown"


def _extract_action(line: str) -> str:
    match = _NODE20_ACTION_RE.search(line)
    if not match:
        return ""
    return match.group("action").rstrip(".,;:)")


def analyze_annotations(text: str) -> dict[str, Any]:
    lines = _lines(text)
    findings: list[dict[str, Any]] = []

    for index, line in enumerate(lines):
        lower = line.lower()

        if "node.js 20 actions are deprecated" in lower:
            action = _extract_action(line)
            findings.append(
                {
                    "id": "github_actions_node20_deprecation",
                    "severity": "warning",
                    "job": _nearest_job(lines, index),
                    "action": action,
                    "title": "GitHub Actions Node.js 20 runtime deprecation",
                    "evidence": line.strip(),
                    "recommendation": (
                        "Update the action to a Node 24-compatible release when available, "
                        "or test the workflow with FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true."
                    ),
                }
            )

        if "python-version" in lower and "input is not set" in lower:
            findings.append(
                {
                    "id": "github_actions_missing_python_version",
                    "severity": "notice",
                    "job": _nearest_job(lines, index),
                    "action": "",
                    "title": "GitHub Actions setup-python version is implicit",
                    "evidence": line.strip(),
                    "recommendation": (
                        "Pin an explicit python-version in the workflow when the source "
                        "workflow is visible; otherwise treat as a generated or managed job."
                    ),
                }
            )

        if (
            "component-detection-dependency-submission-action" in line
            or "component-detection scan" in lower
            or "pipreport" in line
        ):
            findings.append(
                {
                    "id": "github_actions_dependency_submission_annotation_source",
                    "severity": "info",
                    "job": _nearest_job(lines, index),
                    "action": _extract_action(line),
                    "title": "Dependency submission annotation came from component detection",
                    "evidence": line.strip(),
                    "recommendation": (
                        "Do not patch product code for this annotation. Inspect workflow "
                        "ownership first because the job may be GitHub-managed or generated."
                    ),
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in findings:
        key = (
            str(finding.get("id", "")),
            str(finding.get("job", "")),
            str(finding.get("evidence", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)

    warning_count = sum(1 for finding in deduped if finding["severity"] == "warning")
    notice_count = sum(1 for finding in deduped if finding["severity"] == "notice")

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": warning_count == 0,
        "finding_count": len(deduped),
        "warning_count": warning_count,
        "notice_count": notice_count,
        "findings": deduped,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# GitHub Actions annotation hygiene",
        "",
        f"- findings: **{payload.get('finding_count', 0)}**",
        f"- warnings: **{payload.get('warning_count', 0)}**",
        f"- notices: **{payload.get('notice_count', 0)}**",
    ]
    findings = payload.get("findings", [])
    if not isinstance(findings, list) or not findings:
        lines.extend(["", "No GitHub Actions annotation hygiene findings detected."])
        return "\n".join(lines) + "\n"

    lines.append("")
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        lines.extend(
            [
                f"## {finding.get('title', 'Finding')}",
                "",
                f"- id: `{finding.get('id', 'unknown')}`",
                f"- severity: `{finding.get('severity', 'unknown')}`",
                f"- job: `{finding.get('job', 'unknown')}`",
            ]
        )
        action = str(finding.get("action", ""))
        if action:
            lines.append(f"- action: `{action}`")
        lines.extend(
            [
                f"- evidence: {finding.get('evidence', '')}",
                f"- recommendation: {finding.get('recommendation', '')}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def analyze_file(path: Path) -> dict[str, Any]:
    return analyze_annotations(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.github_actions_annotation_hygiene")
    parser.add_argument("annotation_log")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--out")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = analyze_file(Path(args.annotation_log))
    except OSError as exc:
        print(f"error={exc}")
        return 2

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_markdown(payload)
    )

    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 1 if payload.get("warning_count", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
