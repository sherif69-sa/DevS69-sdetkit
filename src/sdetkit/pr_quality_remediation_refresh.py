from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

SCHEMA_VERSION = "sdetkit.pr_quality.remediation_refresh.v1"
DEFAULT_OUT_DIR = Path("build/pr-quality/remediation-refresh")

ASSESS_GREEN_AFTER_SAFE_FIX = "green_after_safe_fix"
ASSESS_GREEN_WITH_PROOF_SIGNAL = "green_with_proof_signal"
ASSESS_STILL_REVIEW_REQUIRED = "still_review_required"
ASSESS_STALE_WAIT_FOR_REFRESHED_CHECKS = "stale_wait_for_refreshed_checks"
ASSESS_BLOCKED_BY_REVIEW_FIRST = "blocked_by_review_first"
ASSESS_BLOCKED_BY_UNKNOWN_FAILURE = "blocked_by_unknown_failure"

REVIEW_FIRST_SURFACES = {
    "security",
    "release",
    "dependency",
    "runtime",
    "type_contract",
    "unknown",
}


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _read_json(path: Path | None) -> JsonObject:
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


def _check_name(check: Mapping[str, Any]) -> str:
    diagnosis = _as_dict(check.get("diagnosis"))
    return (
        _string(check.get("name"))
        or _string(check.get("check"))
        or _string(diagnosis.get("title"))
        or "unknown"
    )


def _failed_check_names(check_intelligence: Mapping[str, Any]) -> list[str]:
    names = [
        _check_name(_as_dict(item))
        for item in _as_list(check_intelligence.get("failed_checks"))
    ]
    return sorted({name for name in names if name})


def _queued_check_names(check_intelligence: Mapping[str, Any]) -> list[str]:
    names = [
        _check_name(_as_dict(item))
        for item in _as_list(check_intelligence.get("queued_checks"))
    ]
    return sorted({name for name in names if name})


def _surface(check: Mapping[str, Any]) -> str:
    diagnosis = _as_dict(check.get("diagnosis"))
    return (
        _string(check.get("surface"))
        or _string(check.get("failure_surface"))
        or _string(diagnosis.get("surface"))
        or _string(diagnosis.get("kind"))
        or "unknown"
    )


def _has_unknown_failure(check_intelligence: Mapping[str, Any]) -> bool:
    for item in _as_list(check_intelligence.get("failed_checks")):
        check = _as_dict(item)
        diagnosis = _as_dict(check.get("diagnosis"))
        surface = _surface(check)
        code = _string(diagnosis.get("code")).lower()
        title = _string(diagnosis.get("title")).lower()
        if surface == "unknown" or code == "unknown" or "unknown failure" in title:
            return True
    return False


def _review_first_blockers(
    *,
    action_report: Mapping[str, Any],
    check_intelligence: Mapping[str, Any],
) -> list[str]:
    blockers: set[str] = set()

    for item in _as_list(check_intelligence.get("failed_checks")):
        check = _as_dict(item)
        diagnosis = _as_dict(check.get("diagnosis"))
        safe = _bool(check.get("safe_to_auto_fix"))
        review_first = _bool(check.get("review_first")) or _bool(diagnosis.get("review_first"))
        surface = _surface(check)
        if review_first or (not safe and surface in REVIEW_FIRST_SURFACES):
            blockers.add(_check_name(check))

    primary = _as_dict(action_report.get("primary_blocker"))
    if primary and _string(action_report.get("status")) == "review_required":
        primary_safe = _bool(primary.get("safe_to_auto_fix"))
        primary_surface = _string(primary.get("surface")) or _surface(primary)
        if not primary_safe or primary_surface in REVIEW_FIRST_SURFACES:
            blockers.add(_check_name(primary))

    return sorted(blockers)


def _safe_fix_outcome_from_sources(
    *,
    action_report: Mapping[str, Any],
    check_intelligence: Mapping[str, Any],
    safe_fix_outcome: Mapping[str, Any] | None,
) -> JsonObject:
    if safe_fix_outcome:
        return dict(safe_fix_outcome)

    from_check = _as_dict(check_intelligence.get("safe_fix_outcome"))
    if from_check:
        return from_check

    return _as_dict(action_report.get("safe_fix_outcome"))


def _first_head_sha(*values: Any) -> str:
    for value in values:
        text = _string(value)
        if text and text != "none":
            return text
    return ""


def build_remediation_refresh(
    *,
    action_report: Mapping[str, Any] | None = None,
    check_intelligence: Mapping[str, Any] | None = None,
    safe_fix_outcome: Mapping[str, Any] | None = None,
    previous_head_sha: str = "",
    refreshed_head_sha: str = "",
) -> JsonObject:
    action_report = _as_dict(action_report)
    check_intelligence = _as_dict(check_intelligence)
    outcome = _safe_fix_outcome_from_sources(
        action_report=action_report,
        check_intelligence=check_intelligence,
        safe_fix_outcome=safe_fix_outcome,
    )

    safe_fix_attempted = _bool(outcome.get("attempted")) or _bool(outcome.get("safe_fix_attempted"))
    safe_fix_committed = _bool(outcome.get("committed")) or _bool(outcome.get("safe_fix_committed"))
    safe_fix_pushed = _bool(outcome.get("pushed")) or _bool(outcome.get("safe_fix_pushed"))
    safe_fix_commit_sha = _first_head_sha(
        outcome.get("commit_sha"),
        outcome.get("safe_fix_commit_sha"),
    ) or "none"

    previous_head = _first_head_sha(
        previous_head_sha,
        outcome.get("previous_head_sha"),
        outcome.get("head_sha"),
        action_report.get("previous_head_sha"),
        check_intelligence.get("previous_head_sha"),
    ) or "unknown"

    refreshed_head = _first_head_sha(
        refreshed_head_sha,
        check_intelligence.get("current_pr_head_sha"),
        check_intelligence.get("pr_head_sha"),
        action_report.get("current_pr_head_sha"),
        action_report.get("refreshed_head_sha"),
        outcome.get("refreshed_head_sha"),
        safe_fix_commit_sha if safe_fix_commit_sha != "none" else "",
    ) or "unknown"

    remaining_failed_checks = _failed_check_names(check_intelligence)
    queued_checks = _queued_check_names(check_intelligence)
    remaining_review_first_blockers = _review_first_blockers(
        action_report=action_report,
        check_intelligence=check_intelligence,
    )

    proof_after_fix_started = safe_fix_pushed and refreshed_head != "unknown"
    proof_after_fix_failed = proof_after_fix_started and bool(remaining_failed_checks)
    proof_after_fix_passed = (
        proof_after_fix_started
        and not remaining_failed_checks
        and not queued_checks
        and not remaining_review_first_blockers
    )

    if _has_unknown_failure(check_intelligence):
        merge_assessment = ASSESS_BLOCKED_BY_UNKNOWN_FAILURE
    elif remaining_review_first_blockers:
        merge_assessment = ASSESS_BLOCKED_BY_REVIEW_FIRST
    elif proof_after_fix_started and queued_checks:
        merge_assessment = ASSESS_STALE_WAIT_FOR_REFRESHED_CHECKS
    elif remaining_failed_checks:
        merge_assessment = ASSESS_STILL_REVIEW_REQUIRED
    elif safe_fix_pushed and proof_after_fix_passed:
        merge_assessment = ASSESS_GREEN_AFTER_SAFE_FIX
    else:
        merge_assessment = ASSESS_GREEN_WITH_PROOF_SIGNAL

    return {
        "schema_version": SCHEMA_VERSION,
        "safe_fix_attempted": safe_fix_attempted,
        "safe_fix_committed": safe_fix_committed,
        "safe_fix_pushed": safe_fix_pushed,
        "safe_fix_commit_sha": safe_fix_commit_sha,
        "previous_head_sha": previous_head,
        "refreshed_head_sha": refreshed_head,
        "proof_after_fix_started": proof_after_fix_started,
        "proof_after_fix_passed": proof_after_fix_passed,
        "proof_after_fix_failed": proof_after_fix_failed,
        "remaining_failed_checks": remaining_failed_checks,
        "remaining_review_first_blockers": remaining_review_first_blockers,
        "queued_checks": queued_checks,
        "merge_assessment": merge_assessment,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    failed = [_string(item) for item in _as_list(payload.get("remaining_failed_checks")) if _string(item)]
    blockers = [
        _string(item)
        for item in _as_list(payload.get("remaining_review_first_blockers"))
        if _string(item)
    ]
    queued = [_string(item) for item in _as_list(payload.get("queued_checks")) if _string(item)]

    lines = [
        "# Remediation refresh",
        "",
        f"- Safe fix attempted: `{str(_bool(payload.get('safe_fix_attempted'))).lower()}`",
        f"- Safe fix committed: `{str(_bool(payload.get('safe_fix_committed'))).lower()}`",
        f"- Safe fix pushed: `{str(_bool(payload.get('safe_fix_pushed'))).lower()}`",
        f"- Safe fix commit SHA: `{_string(payload.get('safe_fix_commit_sha'), 'none')}`",
        f"- Previous head SHA: `{_string(payload.get('previous_head_sha'), 'unknown')}`",
        f"- Refreshed head SHA: `{_string(payload.get('refreshed_head_sha'), 'unknown')}`",
        f"- Proof after fix started: `{str(_bool(payload.get('proof_after_fix_started'))).lower()}`",
        f"- Proof after fix passed: `{str(_bool(payload.get('proof_after_fix_passed'))).lower()}`",
        f"- Proof after fix failed: `{str(_bool(payload.get('proof_after_fix_failed'))).lower()}`",
        f"- Merge assessment: `{_string(payload.get('merge_assessment'), 'unknown')}`",
        "",
        "## Remaining failed checks",
    ]

    lines.extend([f"- `{item}`" for item in failed] or ["- None"])
    lines.append("")
    lines.append("## Remaining review-first blockers")
    lines.extend([f"- `{item}`" for item in blockers] or ["- None"])
    lines.append("")
    lines.append("## Queued checks")
    lines.extend([f"- `{item}`" for item in queued] or ["- None"])
    return "\n".join(lines).strip() + "\n"


def write_remediation_refresh(payload: Mapping[str, Any], out_dir: Path) -> dict[str, str]:
    json_path = out_dir / "remediation-refresh.json"
    markdown_path = out_dir / "remediation-refresh.md"
    _write_json(json_path, payload)
    _write_text(markdown_path, render_markdown(payload))
    return {
        "remediation_refresh_json": json_path.as_posix(),
        "remediation_refresh_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_remediation_refresh")
    parser.add_argument("--action-report-json", default="")
    parser.add_argument("--check-intelligence-json", default="")
    parser.add_argument("--safe-fix-outcome-json", default="")
    parser.add_argument("--previous-head-sha", default="")
    parser.add_argument("--refreshed-head-sha", default="")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_remediation_refresh(
            action_report=_read_json(Path(args.action_report_json)) if args.action_report_json else {},
            check_intelligence=(
                _read_json(Path(args.check_intelligence_json))
                if args.check_intelligence_json
                else {}
            ),
            safe_fix_outcome=(
                _read_json(Path(args.safe_fix_outcome_json))
                if args.safe_fix_outcome_json
                else {}
            ),
            previous_head_sha=args.previous_head_sha,
            refreshed_head_sha=args.refreshed_head_sha,
        )
        artifacts = write_remediation_refresh(payload, Path(args.out_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps({"artifacts": artifacts, "payload": payload}, indent=2, sort_keys=True))
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
