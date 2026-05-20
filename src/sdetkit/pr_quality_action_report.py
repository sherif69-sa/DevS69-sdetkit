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


def _result_title(
    status: str,
    *,
    evidence_signal_present: bool,
    evidence_review_required: bool,
) -> str:
    base = _status_title(status)
    if status != "green":
        return base
    if evidence_review_required:
        return f"{base} with evidence review"
    if evidence_signal_present:
        return f"{base} with proof signal"
    return base


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


def _safe_fix_outcome_lines(outcome: JsonObject) -> list[str]:
    if not outcome:
        return ["- none"]

    files = [_string(item) for item in _as_list(outcome.get("affected_files")) if _string(item)]
    proof_commands = [
        _string(item) for item in _as_list(outcome.get("proof_commands")) if _string(item)
    ]

    lines = [
        f"- Status: `{_string(outcome.get('status') or 'unknown')}`",
        f"- Attempted: `{str(bool(outcome.get('attempted', False))).lower()}`",
        f"- Remediation OK: `{str(bool(outcome.get('remediation_ok', False))).lower()}`",
        f"- Committed: `{str(bool(outcome.get('committed', False))).lower()}`",
        f"- Pushed: `{str(bool(outcome.get('pushed', False))).lower()}`",
        f"- Commit SHA: `{_string(outcome.get('commit_sha') or 'none')}`",
        "- Files: " + (", ".join(f"`{item}`" for item in files) if files else "`none`"),
        f"- Reason: {_string(outcome.get('reason') or 'none')}",
    ]

    if proof_commands:
        lines.append("- Proof after fix:")
        lines.extend(f"  - `{item}`" for item in proof_commands)
    else:
        lines.append("- Proof after fix: none")

    return lines


def _remediation_refresh_lines(refresh: JsonObject) -> list[str]:
    if not refresh:
        return ["none"]

    lines = [
        f"- Safe fix pushed: `{str(bool(refresh.get('safe_fix_pushed', False))).lower()}`",
        f"- Safe fix committed: `{str(bool(refresh.get('safe_fix_committed', False))).lower()}`",
        f"- Safe fix commit SHA: `{_string(refresh.get('safe_fix_commit_sha') or 'none')}`",
        f"- Previous head SHA: `{_string(refresh.get('previous_head_sha') or 'unknown')}`",
        f"- Refreshed head SHA: `{_string(refresh.get('refreshed_head_sha') or 'unknown')}`",
    ]

    if bool(refresh.get("safe_fix_pushed", False)):
        lines.append("- Safe fix pushed to branch.")

    proof_after_fix_passed = bool(refresh.get("proof_after_fix_passed", False))
    proof_after_fix_failed = bool(refresh.get("proof_after_fix_failed", False))
    proof_after_fix_started = bool(refresh.get("proof_after_fix_started", False))
    if proof_after_fix_passed:
        proof_result = "passed"
    elif proof_after_fix_failed:
        proof_result = "failed"
    elif proof_after_fix_started:
        proof_result = "started"
    else:
        proof_result = "not_started"

    lines.append(f"- Proof after fix result: `{proof_result}`")

    failed = [
        _string(item) for item in _as_list(refresh.get("remaining_failed_checks")) if _string(item)
    ]
    blockers = [
        _string(item)
        for item in _as_list(refresh.get("remaining_review_first_blockers"))
        if _string(item)
    ]
    if failed:
        lines.append("- Remaining failed checks: " + ", ".join(f"`{item}`" for item in failed[:8]))
    else:
        lines.append("- Remaining failed checks: none")

    if blockers:
        lines.append("- Remaining blockers: " + ", ".join(f"`{item}`" for item in blockers[:8]))
    else:
        lines.append("- Remaining blockers: none")

    lines.append(f"- Merge assessment: `{_string(refresh.get('merge_assessment') or 'unknown')}`")
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
        first_failure = _as_dict(item.get("first_failure"))
        first_line = _string(first_failure.get("line"))
        if first_line:
            line_number = _int(first_failure.get("line_number"))
            tool = _string(first_failure.get("tool") or "unknown")
            kind = _string(first_failure.get("kind") or "unknown")
            location = f"line {line_number}" if line_number else "line unknown"
            lines.append(f"  - First failure: `{first_line}`")
            lines.append(f"  - Failure location: `{location}`")
            lines.append(f"  - Failure tool/kind: `{tool}` / `{kind}`")
        safe_remediation = _as_dict(item.get("safe_remediation"))
        if bool(safe_remediation.get("safe_to_auto_fix", False)):
            strategy = _string(safe_remediation.get("strategy") or "unknown")
            reason = _string(safe_remediation.get("reason") or "approved safe remediation")
            lines.append(f"  - Safe remediation: `{strategy}`")
            lines.append(f"  - Safe reason: `{reason}`")
        formatter_files = [
            _string(path) for path in _as_list(item.get("formatter_changed_files")) if _string(path)
        ]
        if formatter_files:
            lines.append(
                "  - Formatter changed files: "
                + ", ".join(f"`{path}`" for path in formatter_files[:8])
            )
        if bool(item.get("stale_evidence", False)):
            head_sha = _string(item.get("head_sha") or "unknown")
            current_sha = _string(item.get("current_pr_head_sha") or "unknown")
            lines.append(f"  - Evidence freshness: `stale` (`{head_sha}` != `{current_sha}`)")
        outside_files = [
            _string(path) for path in _as_list(item.get("outside_changed_files")) if _string(path)
        ]
        if outside_files:
            lines.append(
                "  - Outside PR changed set: "
                + ", ".join(f"`{path}`" for path in outside_files[:8])
            )
        if bool(item.get("possible_changed_files_gate_fallout", False)):
            lines.append("  - Gate fallout: possible changed-files base-resolution issue")
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
    first_failure = _as_dict(primary.get("first_failure"))
    first_line = _string(primary.get("first_failure_line") or first_failure.get("line"))
    if first_line:
        line_number = _int(first_failure.get("line_number"))
        tool = _string(first_failure.get("tool") or "unknown")
        kind = _string(first_failure.get("kind") or "unknown")
        location = f"line {line_number}" if line_number else "line unknown"
        lines.append(f"- First failure: `{first_line}`")
        lines.append(f"- Failure location: `{location}`")
        lines.append(f"- Failure tool/kind: `{tool}` / `{kind}`")
    safe_remediation = _as_dict(primary.get("safe_remediation"))
    if bool(safe_remediation.get("safe_to_auto_fix", False)):
        strategy = _string(safe_remediation.get("strategy") or "unknown")
        reason = _string(safe_remediation.get("reason") or "approved safe remediation")
        lines.append(f"- Safe remediation: `{strategy}`")
        lines.append(f"- Safe reason: `{reason}`")

    formatter_files = [
        _string(path) for path in _as_list(primary.get("formatter_changed_files")) if _string(path)
    ]
    if formatter_files:
        lines.append(
            "- Formatter changed files: " + ", ".join(f"`{path}`" for path in formatter_files[:8])
        )

    if bool(primary.get("stale_evidence", False)):
        head_sha = _string(primary.get("head_sha") or "unknown")
        current_sha = _string(primary.get("current_pr_head_sha") or "unknown")
        lines.append(f"- Evidence freshness: `stale` (`{head_sha}` != `{current_sha}`)")

    outside_files = [
        _string(path) for path in _as_list(primary.get("outside_changed_files")) if _string(path)
    ]
    if outside_files:
        lines.append(
            "- Outside PR changed set: " + ", ".join(f"`{path}`" for path in outside_files[:8])
        )

    if bool(primary.get("possible_changed_files_gate_fallout", False)):
        lines.append("- Gate fallout: possible changed-files base-resolution issue")

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


def _required_count(items: list[Any]) -> int:
    return sum(1 for item in items if bool(_as_dict(item).get("required", False)))


def _cleared_security_review_lines(
    *,
    check_intelligence: JsonObject,
    action_report: JsonObject,
    evidence_narrative: JsonObject,
    evidence_review_required: bool,
) -> list[str]:
    if not evidence_review_required:
        return []

    primary = _as_dict(evidence_narrative.get("primary_signal"))
    graph = _as_dict(evidence_narrative.get("graph"))
    top_blocker = _as_dict(graph.get("top_blocker"))
    surface = _string(primary.get("surface") or top_blocker.get("surface") or "")

    if surface != "security":
        return []

    security = _as_dict(
        check_intelligence.get("security_review")
        or _as_dict(action_report.get("evidence")).get("security_review")
    )
    if security.get("collected") is not True:
        return []

    if _int(security.get("unresolved_findings")) != 0:
        return []

    failed = _as_list(check_intelligence.get("failed_checks"))
    queued = _as_list(check_intelligence.get("queued_checks"))
    startup = _as_list(check_intelligence.get("startup_failures"))
    missing_required = _as_list(check_intelligence.get("missing_required_contexts"))

    if failed or missing_required or _required_count(queued) or _required_count(startup):
        return []

    return [
        "- Proof signal: `present`",
        "- Surface: `security`",
        "- Title: Security review cleared for changed code",
        "- Review signal reconciliation: `latest security review has no unresolved PR-owned findings`",
        "- Failed checks: `0`",
        "- Unresolved security findings: `0`",
        "- Security review action: `no fix or dismissal required for PR-owned security findings`",
    ]


def _reconciled_evidence_signal(
    *,
    check_intelligence: JsonObject,
    action_report: JsonObject,
    evidence_narrative: JsonObject,
    heading: str,
    lines: list[str],
    review_required: bool,
) -> tuple[str, list[str], bool]:
    cleared_security = _cleared_security_review_lines(
        check_intelligence=check_intelligence,
        action_report=action_report,
        evidence_narrative=evidence_narrative,
        evidence_review_required=review_required,
    )
    if cleared_security:
        return "Evidence proof signal", cleared_security, False

    return heading, lines, review_required


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

    if review_required:
        lines.extend(
            _evidence_review_clarity_lines(
                quality_ok=_as_dict(evidence_narrative.get("quality")).get("ok") is True,
                surface=surface or top_surface or "unknown",
            )
        )

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


def _evidence_review_clarity_lines(
    *,
    quality_ok: bool,
    surface: str,
) -> list[str]:
    if not quality_ok:
        return []

    lines = [
        "- Gate interpretation: `quality gate passed; evidence review still required`",
        "- Failure status: `not a failed quality gate and not a failed required check`",
        "- Merge impact: `human review required before merge`",
        "- Automation boundary: `no auto-remediation or security dismissal attempted`",
    ]

    if surface == "security":
        lines.append(
            "- Security review action: `fix the PR-owned security finding or dismiss the false positive with a review reason`"
        )
    else:
        lines.append(
            f"- Review action: `review the listed {surface or 'unknown'} evidence before merge`"
        )

    return lines


def _patch_plan_lines(evidence_narrative: JsonObject) -> list[str]:
    patch_plan = _as_dict(evidence_narrative.get("patch_plan"))
    if not patch_plan or not patch_plan.get("enabled"):
        return []

    lines = [
        f"- Status: `{_string(patch_plan.get('status') or 'unknown')}`",
        f"- Source kind: `{_string(patch_plan.get('source_kind') or 'unknown')}`",
        f"- Source code: `{_string(patch_plan.get('source_code') or 'UNKNOWN')}`",
        f"- Safe to auto-fix: `{str(bool(patch_plan.get('safe_to_auto_fix', False))).lower()}`",
        f"- Dry run only: `{str(bool(patch_plan.get('dry_run_only', True))).lower()}`",
        f"- Requires human review: `{str(bool(patch_plan.get('requires_human_review', True))).lower()}`",
        f"- Patch steps: `{int(patch_plan.get('patch_step_count', 0) or 0)}`",
    ]

    proof_commands = [
        str(command)
        for command in _as_list(patch_plan.get("proof_commands"))
        if isinstance(command, str) and command.strip()
    ]
    if proof_commands:
        lines.extend(["- Proof commands:"])
        lines.extend(f"  - `{command}`" for command in proof_commands[:5])

    review_commands = [
        str(command)
        for command in _as_list(patch_plan.get("recommended_commands"))
        if isinstance(command, str) and command.strip()
    ]
    if review_commands:
        lines.extend(["- Review commands:"])
        lines.extend(f"  - `{command}`" for command in review_commands[:5])

    return lines


def render_comment_body(
    *,
    action_report: JsonObject,
    check_intelligence: JsonObject,
    evidence_narrative: JsonObject | None = None,
    safe_fix_outcome: JsonObject | None = None,
) -> str:
    evidence_narrative = evidence_narrative or {}
    safe_fix_outcome = safe_fix_outcome or _as_dict(check_intelligence.get("safe_fix_outcome"))
    remediation_refresh = _as_dict(check_intelligence.get("remediation_refresh"))
    status = _string(action_report.get("status") or "unknown")
    evidence_signal_heading, evidence_signal_lines, evidence_review_required = _evidence_signal(
        evidence_narrative
    )
    evidence_signal_heading, evidence_signal_lines, evidence_review_required = (
        _reconciled_evidence_signal(
            check_intelligence=check_intelligence,
            action_report=action_report,
            evidence_narrative=evidence_narrative,
            heading=evidence_signal_heading,
            lines=evidence_signal_lines,
            review_required=evidence_review_required,
        )
    )

    lines = [
        "## SDETKit Review Result: "
        + _result_title(
            status,
            evidence_signal_present=bool(evidence_signal_lines),
            evidence_review_required=evidence_review_required,
        ),
        "",
        f"Status: `{status}`",
        "",
    ]

    quality = _quality_lines(evidence_narrative)
    if quality:
        lines.extend(["## Quality summary", "", *quality, ""])

    if evidence_signal_lines:
        lines.extend(["## " + evidence_signal_heading, "", *evidence_signal_lines, ""])

    patch_plan = _patch_plan_lines(evidence_narrative)
    if patch_plan:
        lines.extend(["## Review-first patch plan", "", *patch_plan, ""])

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
            "## Safe fix outcome",
            "",
            *_safe_fix_outcome_lines(_as_dict(safe_fix_outcome)),
            "Remediation refresh",
            *_remediation_refresh_lines(_as_dict(remediation_refresh)),
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
                    "- Evidence review signal present; quality gate passed, but review-first evidence requires human review before merge.",
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

    status = _string(action_report.get("status") or "unknown")
    _heading, evidence_signal_lines, evidence_review_required = _evidence_signal(evidence_narrative)
    _heading, evidence_signal_lines, evidence_review_required = _reconciled_evidence_signal(
        check_intelligence=check_intelligence,
        action_report=action_report,
        evidence_narrative=evidence_narrative,
        heading=_heading,
        lines=evidence_signal_lines,
        review_required=evidence_review_required,
    )
    if evidence_review_required:
        evidence_signal_kind = "review"
    elif evidence_signal_lines:
        evidence_signal_kind = "proof"
    else:
        evidence_signal_kind = "none"

    return {
        "out": out.as_posix(),
        "status": status,
        "result_title": _result_title(
            status,
            evidence_signal_present=bool(evidence_signal_lines),
            evidence_review_required=evidence_review_required,
        ),
        "evidence_signal_kind": evidence_signal_kind,
        "evidence_signal_present": bool(evidence_signal_lines),
        "evidence_review_required": evidence_review_required,
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
