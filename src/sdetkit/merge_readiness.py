from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import check_intelligence

MERGE_READINESS_SCHEMA_VERSION = "sdetkit.merge_readiness.v1"

JsonObject = dict[str, Any]

_PENDING_STATUSES = {
    "expected",
    "in_progress",
    "pending",
    "queued",
    "requested",
    "waiting",
}
_FAILED_CONCLUSIONS = {
    "cancelled",
    "failure",
    "startup_failure",
    "timed_out",
}
_SKIPPED_CONCLUSIONS = {"neutral", "skipped"}


def _string(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_state(record: JsonObject, *, stale: bool) -> str:
    status = check_intelligence._check_status(record)
    conclusion = check_intelligence._check_conclusion(record)

    if stale or conclusion == "action_required":
        return "action_required"
    if conclusion in _FAILED_CONCLUSIONS:
        return "failed"
    if conclusion in _SKIPPED_CONCLUSIONS:
        return "skipped"
    if conclusion == "success":
        return "green"
    if status in _PENDING_STATUSES or not conclusion:
        return "pending"
    return "failed"


def _check_summary(
    record: JsonObject,
    *,
    index: int,
    current_head_sha: str,
) -> JsonObject:
    head_sha = check_intelligence._record_head_sha(record)
    stale = bool(current_head_sha and head_sha and head_sha != current_head_sha)
    return {
        "name": check_intelligence._check_name(record, index),
        "state": _check_state(record, stale=stale),
        "status": check_intelligence._check_status(record),
        "conclusion": check_intelligence._check_conclusion(record),
        "required": check_intelligence._check_required(record),
        "url": check_intelligence._record_url(record),
        "head_sha": head_sha,
        "current_head_sha": current_head_sha,
        "stale": stale,
        "missing_required_context": False,
    }


def _missing_required_check(name: str, *, current_head_sha: str) -> JsonObject:
    return {
        "name": name,
        "state": "pending",
        "status": "missing",
        "conclusion": "",
        "required": True,
        "url": "",
        "head_sha": "",
        "current_head_sha": current_head_sha,
        "stale": False,
        "missing_required_context": True,
    }


def _overall_state(required_checks: list[JsonObject]) -> str:
    if not required_checks:
        return "unknown"

    states = {_string(item.get("state")) for item in required_checks}
    if "failed" in states:
        return "failed"
    if states.intersection({"action_required", "skipped"}):
        return "action_required"
    if "pending" in states:
        return "pending"
    if states == {"green"}:
        return "green"
    return "action_required"


def _next_owner_action(overall_state: str, required_checks: list[JsonObject]) -> JsonObject:
    def first(*states: str) -> JsonObject:
        return next(
            (
                item
                for item in required_checks
                if _string(item.get("state")) in set(states)
            ),
            {},
        )

    if overall_state == "failed":
        check = first("failed")
        return {
            "check": _string(check.get("name")),
            "action": (
                "Open the failed required check, fix the first real failing contract, "
                "then refresh this report on the current head."
            ),
            "url": _string(check.get("url")),
        }

    if overall_state == "action_required":
        stale = next((item for item in required_checks if bool(item.get("stale"))), {})
        if stale:
            return {
                "check": _string(stale.get("name")),
                "action": (
                    "Refresh or rerun this required check for the current head before "
                    "treating its result as merge evidence."
                ),
                "url": _string(stale.get("url")),
            }

        check = first("action_required", "skipped")
        if _string(check.get("state")) == "skipped":
            action = (
                "Inspect the required check trigger or condition, run the correct check "
                "for this head, and refresh the report."
            )
        else:
            action = (
                "Open the workflow run, complete the required approval or start action, "
                "then refresh the report."
            )
        return {
            "check": _string(check.get("name")),
            "action": action,
            "url": _string(check.get("url")),
        }

    if overall_state == "pending":
        check = first("pending")
        action = (
            "Provide or start the missing required check, then refresh the report."
            if bool(check.get("missing_required_context"))
            else "Wait for the required check to complete, then refresh the report."
        )
        return {
            "check": _string(check.get("name")),
            "action": action,
            "url": _string(check.get("url")),
        }

    if overall_state == "green":
        return {
            "check": "",
            "action": (
                "No required-check action is pending. Human review still owns the merge decision."
            ),
            "url": "",
        }

    return {
        "check": "",
        "action": (
            "Provide required-context metadata before using check results as merge-readiness evidence."
        ),
        "url": "",
    }


def _state_counts(checks: list[JsonObject]) -> JsonObject:
    states = ("green", "pending", "failed", "skipped", "action_required")
    return {
        state: sum(1 for item in checks if _string(item.get("state")) == state)
        for state in states
    }


def build_merge_readiness(
    *,
    checks_json: Path,
    current_head_sha: str = "",
) -> JsonObject:
    payload = _read_json(checks_json)
    records = check_intelligence._iter_check_records(payload)
    required_contexts = set(check_intelligence._required_contexts(payload))
    seen_identities: set[str] = set()
    checks: list[JsonObject] = []

    for index, record in enumerate(records):
        seen_identities.update(check_intelligence._record_identities(record, index=index))
        checks.append(
            _check_summary(
                record,
                index=index,
                current_head_sha=current_head_sha,
            )
        )

    missing_required_contexts = sorted(required_contexts - seen_identities)
    checks.extend(
        _missing_required_check(name, current_head_sha=current_head_sha)
        for name in missing_required_contexts
    )

    required_checks = [item for item in checks if bool(item.get("required"))]
    optional_checks = [item for item in checks if not bool(item.get("required"))]
    overall_state = _overall_state(required_checks)

    return {
        "schema_version": MERGE_READINESS_SCHEMA_VERSION,
        "status": overall_state,
        "current_head_sha": current_head_sha,
        "observed_required_checks_green": bool(
            required_checks and all(item.get("state") == "green" for item in required_checks)
        ),
        "checks": checks,
        "required_checks": required_checks,
        "optional_checks": optional_checks,
        "missing_required_contexts": missing_required_contexts,
        "counts": {
            "all": _state_counts(checks),
            "required": _state_counts(required_checks),
            "optional": _state_counts(optional_checks),
        },
        "next_owner_action": _next_owner_action(overall_state, required_checks),
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def render_merge_readiness(report: JsonObject) -> str:
    lines = [
        "# SDETKit Merge Readiness",
        "",
        f"Status: `{_string(report.get('status'))}`",
        f"Current head: `{_string(report.get('current_head_sha')) or 'unknown'}`",
        "",
        "| Required | Check | State | Conclusion | Stale |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report.get("checks", []):
        check = item if isinstance(item, dict) else {}
        lines.append(
            "| {required} | {name} | {state} | {conclusion} | {stale} |".format(
                required="yes" if bool(check.get("required")) else "no",
                name=_string(check.get("name")),
                state=_string(check.get("state")),
                conclusion=_string(check.get("conclusion")) or "n/a",
                stale="yes" if bool(check.get("stale")) else "no",
            )
        )

    action = report.get("next_owner_action")
    owner_action = action if isinstance(action, dict) else {}
    lines.extend(
        [
            "",
            "## Next owner action",
            "",
            f"- Check: `{_string(owner_action.get('check')) or 'none'}`",
            f"- Action: {_string(owner_action.get('action'))}",
            f"- URL: {_string(owner_action.get('url')) or 'n/a'}",
            "",
            "## Authority boundary",
            "",
            "- Reporting only: `true`",
            "- Automation allowed: `false`",
            "- Patch application allowed: `false`",
            "- Merge authorized: `false`",
            "- Semantic equivalence proven: `false`",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(*, report: JsonObject, out_dir: Path) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "merge-readiness.json"
    markdown_path = out_dir / "merge-readiness.md"
    _write_json(json_path, report)
    markdown_path.write_text(render_merge_readiness(report), encoding="utf-8")
    return {
        "merge_readiness": json_path.as_posix(),
        "merge_readiness_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.merge_readiness")
    parser.add_argument("--checks-json", type=Path, required=True)
    parser.add_argument("--current-head-sha", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("build/pr-quality"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_merge_readiness(
        checks_json=args.checks_json,
        current_head_sha=args.current_head_sha,
    )
    artifacts = write_artifacts(report=report, out_dir=args.out_dir)
    sys.stdout.write(json.dumps(artifacts, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
