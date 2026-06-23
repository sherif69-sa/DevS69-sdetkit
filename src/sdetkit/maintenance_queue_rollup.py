from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import automation_health as automation_health_report
from . import issue_queue_classifier as issue_queue_report
from . import security_followup_disposition as security_followup_report
from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    collect_source_run_ids,
    extract_source_issue_numbers,
    render_freshness_text,
)

SCHEMA_VERSION = "sdetkit.maintenance.queue.rollup.v2"
DEFAULT_OUT = "build/sdetkit/maintenance-queue-rollup.json"
GENERATOR_SOURCE = "src/sdetkit/maintenance_queue_rollup.py"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _issue_number(item: dict[str, Any]) -> int:
    return _as_int(item.get("issue_number"), 0)


def _issue_lane(classification: str) -> str:
    if classification == "security_followup":
        return "security"
    if classification in {"automation_health_gap", "workflow_governance"}:
        return "automation"
    if classification == "docs_operator_gap":
        return "docs"
    if classification == "product_roadmap_gap":
        return "roadmap"
    if classification == "generated_tracker":
        return "command center"
    return "triage"


def _security_by_issue(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {_issue_number(item): item for item in _as_list(payload, "dispositions")}


def _automation_by_issue(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {_issue_number(item): item for item in _as_list(payload, "automation_signals")}


def _score_item(
    *,
    issue: dict[str, Any],
    automation: dict[str, Any] | None,
    security: dict[str, Any] | None,
) -> int:
    score = _as_int(issue.get("priority_score"), 0)
    classification = str(issue.get("classification", ""))

    if security is not None:
        if bool(security.get("review_required")):
            score += 600
        elif bool(security.get("close_candidate")):
            score += 120

    if automation is not None:
        health_state = str(automation.get("health_state", ""))
        if health_state == "possible_blocker_review_required":
            score += 350
        elif health_state == "review_required":
            score += 200
        else:
            score += 80

    if classification == "generated_tracker":
        score -= 100
    if classification == "stale_or_superseded":
        score -= 200

    return max(score, 0)


def _review_required(
    *,
    issue: dict[str, Any],
    automation: dict[str, Any] | None,
    security: dict[str, Any] | None,
) -> bool:
    if security is not None:
        return bool(security.get("review_required"))
    if automation is not None:
        return str(automation.get("health_state")) in {
            "possible_blocker_review_required",
            "review_required",
        }
    return str(issue.get("blocking_status", "")) in {
        "possible_blocker_needs_security_review",
        "review_required",
        "blocking_until_proven_resolved",
    }


def _close_candidate(
    *,
    issue: dict[str, Any],
    security: dict[str, Any] | None,
) -> bool:
    classification = str(issue.get("classification", ""))
    if security is not None:
        return bool(security.get("close_candidate"))
    return classification in {"generated_tracker", "stale_or_superseded"}


def _recommended_action(
    *,
    issue: dict[str, Any],
    automation: dict[str, Any] | None,
    security: dict[str, Any] | None,
) -> str:
    if security is not None:
        action = str(security.get("recommended_action", "")).strip()
        if action:
            return action
    if automation is not None:
        action = str(automation.get("recommended_action", "")).strip()
        if action:
            return action
    action = str(issue.get("recommended_action", "")).strip()
    if action:
        return action.replace("_", " ")
    return "review this queue item"


def build_maintenance_queue_rollup(
    issue_queue: dict[str, Any],
    automation_health: dict[str, Any],
    security_followup: dict[str, Any],
) -> dict[str, Any]:
    automation_lookup = _automation_by_issue(automation_health)
    security_lookup = _security_by_issue(security_followup)

    queue_items: list[dict[str, Any]] = []
    for issue in _as_list(issue_queue, "issues"):
        number = _issue_number(issue)
        if number == 0:
            continue

        classification = str(issue.get("classification", "needs_human_review"))
        automation = automation_lookup.get(number)
        security = security_lookup.get(number)
        review_required = _review_required(
            issue=issue,
            automation=automation,
            security=security,
        )
        close_candidate = _close_candidate(issue=issue, security=security)
        rank_score = _score_item(issue=issue, automation=automation, security=security)

        queue_items.append(
            {
                "issue_number": number,
                "title": str(issue.get("title", "")),
                "lane": _issue_lane(classification),
                "classification": classification,
                "rank_score": rank_score,
                "review_required": review_required,
                "close_candidate": close_candidate,
                "security_disposition": (
                    str(security.get("disposition", "")) if security is not None else None
                ),
                "automation_health_state": (
                    str(automation.get("health_state", "")) if automation is not None else None
                ),
                "recommended_action": _recommended_action(
                    issue=issue,
                    automation=automation,
                    security=security,
                ),
                **AUTHORITY_BOUNDARY,
            }
        )

    queue_items.sort(
        key=lambda item: (
            not bool(item["review_required"]),
            -int(item["rank_score"]),
            int(item["issue_number"]),
        )
    )
    primary = queue_items[0] if queue_items else None

    review_required_count = sum(1 for item in queue_items if bool(item["review_required"]))
    close_candidate_count = sum(1 for item in queue_items if bool(item["close_candidate"]))

    if review_required_count:
        status = "review required"
    elif queue_items:
        status = "ready with proof"
    else:
        status = "empty"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_issue_count": _as_int(issue_queue.get("source_issue_count"), len(queue_items)),
        "queue_item_count": len(queue_items),
        "review_required_count": review_required_count,
        "close_candidate_count": close_candidate_count,
        "primary_issue": primary["issue_number"] if primary else None,
        "recommended_next_action": primary["recommended_action"] if primary else None,
        "queue_items": queue_items,
        "input_artifacts": {
            "issue_queue_schema_version": str(issue_queue.get("schema_version", "")),
            "automation_health_schema_version": str(automation_health.get("schema_version", "")),
            "security_schema": str(security_followup.get("schema_version", "")),
        },
        **AUTHORITY_BOUNDARY,
    }


EXPECTED_INPUT_SCHEMAS = {
    "issue_queue": issue_queue_report.SCHEMA_VERSION,
    "automation_health": automation_health_report.SCHEMA_VERSION,
    "security_followup": security_followup_report.SCHEMA_VERSION,
}


def _input_schemas(
    issue_queue: Mapping[str, Any],
    automation_health: Mapping[str, Any],
    security_followup: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "issue_queue": str(issue_queue.get("schema_version", "")),
        "automation_health": str(automation_health.get("schema_version", "")),
        "security_followup": str(security_followup.get("schema_version", "")),
    }


def _validate_input_schemas(
    issue_queue: Mapping[str, Any],
    automation_health: Mapping[str, Any],
    security_followup: Mapping[str, Any],
) -> None:
    actual = _input_schemas(issue_queue, automation_health, security_followup)
    mismatches = {
        key: {"actual": actual.get(key, ""), "expected": expected}
        for key, expected in EXPECTED_INPUT_SCHEMAS.items()
        if actual.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"unsupported maintenance queue input schemas: {mismatches}")


def maintenance_queue_rollup_input_provenance(
    *,
    issue_queue_json: str | Path,
    automation_health_json: str | Path,
    security_followup_json: str | Path,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generator_path: str | Path | None = None,
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    issue_path = Path(issue_queue_json)
    automation_path = Path(automation_health_json)
    security_path = Path(security_followup_json)
    issue_queue = _load_dict(issue_path)
    automation_health = _load_dict(automation_path)
    security_followup = _load_dict(security_path)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )

    raw_issues = _as_list(issue_queue, "issues")
    issue_numbers = extract_source_issue_numbers(raw_issues)
    run_ids = collect_source_run_ids(
        source_run_ids,
        payloads=(issue_queue, automation_health, security_followup),
    )
    schemas = _input_schemas(issue_queue, automation_health, security_followup)

    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=generator.read_bytes(),
        data_inputs={
            "issue_queue_json": issue_path.read_bytes(),
            "automation_health_json": automation_path.read_bytes(),
            "security_followup_json": security_path.read_bytes(),
        },
        root=root,
        source_issue_numbers=issue_numbers,
        source_run_ids=run_ids,
        input_artifact_schemas=schemas,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def check_maintenance_queue_rollup_freshness(
    *,
    issue_queue_json: str | Path,
    automation_health_json: str | Path,
    security_followup_json: str | Path,
    report_path: str | Path,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    issue_queue = _load_dict(issue_queue_json)
    automation_health = _load_dict(automation_health_json)
    security_followup = _load_dict(security_followup_json)
    current = maintenance_queue_rollup_input_provenance(
        issue_queue_json=issue_queue_json,
        automation_health_json=automation_health_json,
        security_followup_json=security_followup_json,
        root=root,
        source_run_ids=source_run_ids,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )
    result = check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )
    if _input_schemas(issue_queue, automation_health, security_followup) != EXPECTED_INPUT_SCHEMAS:
        result["reasons"] = sorted(set([*result["reasons"], "input_artifact_schema_mismatch"]))
        result["status"] = "stale"
        result["fresh"] = False
    return result


def write_maintenance_queue_rollup_artifact(
    *,
    issue_queue_json: str | Path,
    automation_health_json: str | Path,
    security_followup_json: str | Path,
    out: str | Path = DEFAULT_OUT,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    issue_queue = _load_dict(issue_queue_json)
    automation_health = _load_dict(automation_health_json)
    security_followup = _load_dict(security_followup_json)
    _validate_input_schemas(issue_queue, automation_health, security_followup)

    payload = build_maintenance_queue_rollup(
        issue_queue,
        automation_health,
        security_followup,
    )
    provenance = maintenance_queue_rollup_input_provenance(
        issue_queue_json=issue_queue_json,
        automation_health_json=automation_health_json,
        security_followup_json=security_followup_json,
        root=root,
        source_run_ids=source_run_ids,
        generated_at=generated_at,
        current_head_sha=current_head_sha,
    )
    payload = attach_provenance(payload, provenance)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit maintenance-queue-rollup",
        description="Build a read-only maintenance queue rollup from diagnostic artifacts.",
    )
    parser.add_argument("--issue-queue-json", required=True)
    parser.add_argument("--automation-health-json", required=True)
    parser.add_argument("--security-followup-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-run-id", action="append", type=int, default=[])
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Check the existing report against current inputs without rewriting it.",
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_maintenance_queue_rollup_freshness(
            issue_queue_json=ns.issue_queue_json,
            automation_health_json=ns.automation_health_json,
            security_followup_json=ns.security_followup_json,
            report_path=ns.out,
            root=ns.root,
            source_run_ids=ns.source_run_id,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_maintenance_queue_rollup_artifact(
        issue_queue_json=ns.issue_queue_json,
        automation_health_json=ns.automation_health_json,
        security_followup_json=ns.security_followup_json,
        out=ns.out,
        root=ns.root,
        source_run_ids=ns.source_run_id,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"rollup_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"queue_items={payload['queue_item_count']}\n")
        sys.stdout.write(f"primary_issue={payload['primary_issue']}\n")
        sys.stdout.write(f"current_head_sha={payload['current_head_sha']}\n")
        sys.stdout.write(f"input_digest={payload['input_provenance']['input_digest']}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
