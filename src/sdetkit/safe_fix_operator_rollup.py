from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
SCHEMA_VERSION = "sdetkit.operator.safe_fix_outcome_rollup.v1"


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _safe_outcomes(check_intelligence: JsonObject) -> list[JsonObject]:
    outcome = _as_dict(check_intelligence.get("safe_fix_outcome"))
    if outcome:
        return [outcome]

    outcomes = [
        _as_dict(item)
        for item in _as_list(check_intelligence.get("safe_fix_outcomes"))
        if isinstance(item, dict)
    ]
    return [item for item in outcomes if item]


def _failed_checks(check_intelligence: JsonObject) -> list[JsonObject]:
    return [
        _as_dict(item)
        for item in _as_list(check_intelligence.get("failed_checks"))
        if isinstance(item, dict)
    ]


def _files_from_outcomes(outcomes: list[JsonObject]) -> list[JsonObject]:
    counts: dict[str, int] = {}
    for outcome in outcomes:
        for item in _as_list(outcome.get("affected_files")):
            path = _string(item)
            if not path:
                continue
            counts[path] = counts.get(path, 0) + 1

    return [
        {"path": path, "count": count}
        for path, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _refusal_reasons(outcomes: list[JsonObject]) -> list[JsonObject]:
    counts: dict[str, int] = {}
    for outcome in outcomes:
        status = _string(outcome.get("status"), "unknown")
        if status in {"pushed", "committed_not_pushed", "remediated_not_committed"}:
            continue
        reason = _string(outcome.get("reason"), "unknown")
        counts[reason] = counts.get(reason, 0) + 1

    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _recommendation(
    *,
    pushed_count: int,
    committed_count: int,
    remediation_ok_count: int,
    attempted_count: int,
    review_first_blocker_count: int,
    refusal_count: int,
) -> JsonObject:
    if pushed_count:
        return {
            "action": "rerun_proof",
            "reason": "At least one safe fix was pushed; rerun required proof on the refreshed branch.",
        }
    if committed_count:
        return {
            "action": "inspect_commit_push",
            "reason": "A safe fix was committed but not pushed; inspect branch/token guardrails.",
        }
    if remediation_ok_count:
        return {
            "action": "inspect_commit_guard",
            "reason": "Safe remediation succeeded but did not produce a commit.",
        }
    if review_first_blocker_count or refusal_count:
        return {
            "action": "review_blockers",
            "reason": "Safe mutation was blocked by review-first failures or missing affected files.",
        }
    if attempted_count:
        return {
            "action": "inspect_failed_safe_fix",
            "reason": "Safe fix was attempted but did not complete successfully.",
        }
    return {
        "action": "no_action",
        "reason": "No safe fix was attempted or needed.",
    }


def build_rollup(check_intelligence: JsonObject) -> JsonObject:
    check_intelligence = _as_dict(check_intelligence)
    outcomes = _safe_outcomes(check_intelligence)
    failed = _failed_checks(check_intelligence)

    attempted_count = sum(1 for item in outcomes if _truthy(item.get("attempted")))
    remediation_ok_count = sum(1 for item in outcomes if _truthy(item.get("remediation_ok")))
    committed_count = sum(1 for item in outcomes if _truthy(item.get("committed")))
    pushed_count = sum(1 for item in outcomes if _truthy(item.get("pushed")))
    not_attempted_count = sum(
        1 for item in outcomes if _string(item.get("status")) == "not_attempted"
    )
    refusal_count = sum(
        1
        for item in outcomes
        if _string(item.get("status")) in {"not_attempted", "attempted_without_success"}
    )

    safe_candidate_count = sum(1 for item in failed if _truthy(item.get("safe_to_auto_fix")))
    review_first_blocker_count = sum(
        1 for item in failed if not _truthy(item.get("safe_to_auto_fix"))
    )

    if pushed_count:
        status = "pushed"
    elif committed_count:
        status = "committed_not_pushed"
    elif remediation_ok_count:
        status = "remediated_not_committed"
    elif review_first_blocker_count or refusal_count:
        status = "blocked_by_review_first"
    elif attempted_count:
        status = "attempted_without_success"
    else:
        status = "not_attempted"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "outcome_count": len(outcomes),
        "attempted_count": attempted_count,
        "remediation_ok_count": remediation_ok_count,
        "committed_count": committed_count,
        "pushed_count": pushed_count,
        "not_attempted_count": not_attempted_count,
        "refusal_count": refusal_count,
        "safe_candidate_count": safe_candidate_count,
        "review_first_blocker_count": review_first_blocker_count,
        "recurring_files": _files_from_outcomes(outcomes),
        "refusal_reasons": _refusal_reasons(outcomes),
        "recommendation": _recommendation(
            pushed_count=pushed_count,
            committed_count=committed_count,
            remediation_ok_count=remediation_ok_count,
            attempted_count=attempted_count,
            review_first_blocker_count=review_first_blocker_count,
            refusal_count=refusal_count,
        ),
    }


def render_markdown(rollup: JsonObject) -> str:
    rollup = _as_dict(rollup)
    recommendation = _as_dict(rollup.get("recommendation"))

    lines = [
        "# Operator safe-fix outcome rollup",
        "",
        f"- Status: `{_string(rollup.get('status'), 'unknown')}`",
        f"- Outcomes: `{int(rollup.get('outcome_count', 0) or 0)}`",
        f"- Attempted: `{int(rollup.get('attempted_count', 0) or 0)}`",
        f"- Remediation OK: `{int(rollup.get('remediation_ok_count', 0) or 0)}`",
        f"- Committed: `{int(rollup.get('committed_count', 0) or 0)}`",
        f"- Pushed: `{int(rollup.get('pushed_count', 0) or 0)}`",
        f"- Safe candidates: `{int(rollup.get('safe_candidate_count', 0) or 0)}`",
        f"- Review-first blockers: `{int(rollup.get('review_first_blocker_count', 0) or 0)}`",
        "",
        "## Recommendation",
        "",
        f"- Action: `{_string(recommendation.get('action'), 'unknown')}`",
        f"- Reason: {_string(recommendation.get('reason'), 'none')}",
        "",
        "## Recurring safe-fix files",
        "",
    ]

    files = [_as_dict(item) for item in _as_list(rollup.get("recurring_files"))]
    if files:
        for item in files[:10]:
            lines.append(f"- `{_string(item.get('path'))}` seen `{int(item.get('count', 0) or 0)}` time(s)")
    else:
        lines.append("- none")

    lines.extend(["", "## Refusal reasons", ""])
    reasons = [_as_dict(item) for item in _as_list(rollup.get("refusal_reasons"))]
    if reasons:
        for item in reasons[:10]:
            lines.append(
                f"- `{_string(item.get('reason'), 'unknown')}` seen `{int(item.get('count', 0) or 0)}` time(s)"
            )
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def write_rollup(check_intelligence: JsonObject, out_dir: Path) -> JsonObject:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rollup = build_rollup(check_intelligence)
    (out_dir / "safe-fix-outcome-rollup.json").write_text(
        json.dumps(rollup, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "safe-fix-outcome-rollup.md").write_text(
        render_markdown(rollup),
        encoding="utf-8",
    )
    return rollup
