from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

BANNED_EDUCATIONAL_PHRASES = (
    "Quality is green, so the review focus is not coverage.",
    "The comment must guide maintainers toward the changed risk surface.",
    "Review the security evidence against the PR diff.",
    "Confirm the graph findings match the changed files and artifacts.",
    "PR Quality evidence affects the comment maintainers use",
)


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _as_dict(payload)


def _string(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _status_title(status: str) -> str:
    return {
        "green": "Green",
        "incomplete": "Checks incomplete",
        "review_required": "Action required",
        "safe_fix_available": "Safe fix available",
    }.get(status, status.replace("_", " ").title() or "Unknown")


def _quality_lines(evidence_narrative: JsonObject) -> list[str]:
    quality = _as_dict(evidence_narrative.get("quality"))
    if not quality:
        return []

    ok = quality.get("ok")
    coverage = (
        quality.get("coverage")
        or quality.get("coverage_percent")
        or quality.get("coverage_pct")
        or ""
    )

    lines: list[str] = []
    if ok is True:
        lines.append("- Quality gate: `passed`")
    elif ok is False:
        lines.append("- Quality gate: `failed`")

    if coverage not in {"", None}:
        lines.append(f"- Coverage: `{coverage}`")

    return lines


def _evidence_lines(check_intelligence: JsonObject, action_report: JsonObject) -> list[str]:
    security = _as_dict(
        check_intelligence.get("security_review")
        or _as_dict(action_report.get("evidence")).get("security_review")
    )
    failed_count = len(_as_list(check_intelligence.get("failed_checks")))
    queued = [_as_dict(item) for item in _as_list(check_intelligence.get("queued_checks"))]
    startup = [_as_dict(item) for item in _as_list(check_intelligence.get("startup_failures"))]
    queued_count = len(queued)
    startup_count = len(startup)
    required_queued_count = len([item for item in queued if bool(item.get("required", False))])
    required_startup_count = len([item for item in startup if bool(item.get("required", False))])
    missing_required_count = len(_as_list(check_intelligence.get("missing_required_contexts")))
    checks_seen = _int(check_intelligence.get("checks_seen"))
    unresolved_security = _int(security.get("unresolved_findings"))

    lines = [
        f"- Checks seen: `{checks_seen}`",
        f"- Failed checks: `{failed_count}`",
        f"- Queued checks: `{queued_count}`",
        f"- Required queued checks: `{required_queued_count}`",
        f"- Missing required contexts: `{missing_required_count}`",
        f"- Startup failures: `{startup_count}`",
        f"- Required startup failures: `{required_startup_count}`",
    ]

    if security:
        collected = "true" if bool(security.get("collected", False)) else "false"
        lines.append(f"- Security review collected: `{collected}`")
        lines.append(f"- Unresolved security findings: `{unresolved_security}`")

    return lines


def _failed_check_lines(check_intelligence: JsonObject) -> list[str]:
    failed = [_as_dict(item) for item in _as_list(check_intelligence.get("failed_checks"))]
    if not failed:
        return ["- none"]

    lines: list[str] = []
    for item in failed[:5]:
        diagnosis = _as_dict(item.get("diagnosis"))
        name = _string(item.get("name"))
        code = _string(diagnosis.get("code") or "unknown")
        title = _string(diagnosis.get("title") or "Unknown failure")
        safe = str(bool(item.get("safe_to_auto_fix", False))).lower()
        lines.append(f"- `{name}` -> {title} (`{code}`), safe_to_auto_fix=`{safe}`")
    return lines


def _primary_blocker_lines(primary: JsonObject) -> list[str]:
    if not primary:
        return ["- none"]

    lines = [
        f"- Check/source: `{primary.get('check', '')}`",
        f"- Title: {primary.get('title', '')}",
        f"- Surface: `{primary.get('surface', '')}`",
        f"- Code: `{primary.get('code', '')}`",
    ]

    path = _string(primary.get("path"))
    line = _string(primary.get("line"))
    if path:
        location = f"{path}:{line}" if line else path
        lines.append(f"- File: `{location}`")

    url = _string(primary.get("url"))
    if url:
        lines.append(f"- URL: {url}")

    impact = _string(primary.get("impact"))
    if impact:
        lines.append(f"- Impact: {impact}")

    return lines


def _automation_lines(action_report: JsonObject) -> list[str]:
    automation = _as_dict(action_report.get("automation"))
    return [
        f"- Attempted: `{str(bool(automation.get('attempted', False))).lower()}`",
        f"- Allowed: `{str(bool(automation.get('allowed', False))).lower()}`",
        f"- Reason: {automation.get('reason', '')}",
    ]


def _bullet_lines(values: list[Any], *, none_text: str = "none") -> list[str]:
    items = [str(item) for item in values if isinstance(item, str) and item.strip()]
    return [f"- {item}" for item in items] or [f"- {none_text}"]


def _command_lines(values: list[Any]) -> list[str]:
    items = [str(item) for item in values if isinstance(item, str) and item.strip()]
    return [f"- `{item}`" for item in items] or ["- none"]


def _evidence_signal(evidence_narrative: JsonObject) -> tuple[str, list[str], bool]:
    primary = _as_dict(evidence_narrative.get("primary_signal"))
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))

    kind = _string(primary.get("kind") or "")
    title = _string(primary.get("title") or top_blocker.get("title") or "")
    surface = _string(primary.get("surface") or top_blocker.get("surface") or "unknown")
    action = _string(top_blocker.get("action") or "")
    top_title = _string(top_blocker.get("title") or "")
    top_surface = _string(top_blocker.get("surface") or "")
    review_first_count = _int(graph.get("review_first_count"))
    critical_count = _int(graph.get("critical_count"))
    top_review_first = bool(top_blocker.get("review_first", False))

    has_narrative_signal = kind in {"review_signal", "integration_proof"}
    has_top_blocker = bool(top_title) and top_title != "none" and top_surface != "none"
    if not has_narrative_signal and not has_top_blocker:
        return "", [], False

    review_required = (
        review_first_count > 0 or critical_count > 0 or action == "review" or top_review_first
    )
    signal_label = "Review signal" if review_required else "Proof signal"

    lines = [
        f"- {signal_label}: `present`",
        f"- Surface: `{surface or 'unknown'}`",
        f"- Title: {title or top_title or 'Evidence graph finding'}",
        f"- Graph nodes: `{_int(graph.get('node_count'))}`",
        f"- Review-first nodes: `{review_first_count}`",
        f"- Critical nodes: `{critical_count}`",
    ]

    if action:
        lines.append(f"- Operator action: `{action}`")
    if isinstance(top_blocker.get("review_first"), bool):
        lines.append(f"- Review first: `{str(top_blocker.get('review_first')).lower()}`")

    proof_commands = [
        str(item)
        for item in _as_list(evidence_narrative.get("next_proof"))
        if isinstance(item, str) and item.strip()
    ]
    if proof_commands:
        lines.extend(["- Next proof:"])
        lines.extend(f"  - `{command}`" for command in proof_commands[:5])

    heading = "Evidence review signal" if review_required else "Evidence proof signal"
    return heading, lines, review_required


def render_comment_body(
    *,
    action_report: JsonObject,
    check_intelligence: JsonObject,
    evidence_narrative: JsonObject | None = None,
) -> str:
    evidence_narrative = evidence_narrative or {}
    status = _string(action_report.get("status") or "unknown")

    lines = [
        f"## SDETKit Review Result: {_status_title(status)}",
        "",
        f"Status: `{status}`",
        "",
    ]

    quality = _quality_lines(evidence_narrative)
    if quality:
        lines.extend(["## Quality summary", "", *quality, ""])

    evidence_signal_heading, evidence_signal_lines, evidence_review_required = _evidence_signal(
        evidence_narrative
    )
    if evidence_signal_lines:
        lines.extend(["## " + evidence_signal_heading, "", *evidence_signal_lines, ""])

    lines.extend(
        [
            "## Primary blocker",
            "",
            *_primary_blocker_lines(_as_dict(action_report.get("primary_blocker"))),
            "",
            "## Automation decision",
            "",
            *_automation_lines(action_report),
            "",
            "## Evidence collected",
            "",
            *_evidence_lines(check_intelligence, action_report),
            "",
            "## Failed check diagnoses",
            "",
            *_failed_check_lines(check_intelligence),
            "",
            "## Recommended actions",
            "",
            *_bullet_lines(_as_list(action_report.get("recommended_actions"))),
            "",
            "## Required proof",
            "",
            *_command_lines(_as_list(action_report.get("proof_commands"))),
            "",
        ]
    )

    if status == "green":
        if evidence_review_required:
            lines.extend(
                [
                    "## Merge assessment",
                    "",
                    "- Evidence review signal present; review the listed surface before merge.",
                    "",
                ]
            )
        elif evidence_signal_lines:
            lines.extend(
                [
                    "## Merge assessment",
                    "",
                    "- Evidence proof signal present; verify the listed proof before routine merge.",
                    "",
                ]
            )
        else:
            lines.extend(["## Merge assessment", "", "- No action required from SDETKit.", ""])

    rendered = "\n".join(lines)
    for phrase in BANNED_EDUCATIONAL_PHRASES:
        if phrase in rendered:
            raise ValueError(f"educational PR Quality phrase leaked into action report: {phrase}")
    return rendered


def write_comment_body(
    *,
    action_report_path: Path,
    check_intelligence_path: Path,
    out: Path,
    evidence_narrative_path: Path | None = None,
) -> JsonObject:
    action_report = _read_json(action_report_path)
    check_intelligence = _read_json(check_intelligence_path)
    evidence_narrative = _read_json(evidence_narrative_path)

    body = render_comment_body(
        action_report=action_report,
        check_intelligence=check_intelligence,
        evidence_narrative=evidence_narrative,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")

    return {
        "out": out.as_posix(),
        "status": _string(action_report.get("status") or "unknown"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_action_report")
    parser.add_argument("--action-report", type=Path, required=True)
    parser.add_argument("--check-intelligence", type=Path, required=True)
    parser.add_argument("--evidence-narrative", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = write_comment_body(
        action_report_path=args.action_report,
        check_intelligence_path=args.check_intelligence,
        evidence_narrative_path=args.evidence_narrative,
        out=args.out,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
