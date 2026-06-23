from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import issue_queue_classifier as issue_queue_report
from .issue_queue_classifier import classify_issues
from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    collect_source_run_ids,
    extract_source_issue_numbers,
    render_freshness_text,
)

SCHEMA_VERSION = "sdetkit.automation_health.v2"
DEFAULT_OUT = "build/sdetkit/automation-health.json"
GENERATOR_SOURCE = "src/sdetkit/automation_health.py"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

AUTOMATION_RELEVANT_CLASSES = {
    "automation_health_gap",
    "generated_tracker",
    "security_followup",
    "workflow_governance",
}


def _load_issues(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_issues = payload
    elif isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        raw_issues = payload["issues"]
    else:
        raise ValueError("issues JSON must be a list or an object with an issues list")
    return [item for item in raw_issues if isinstance(item, dict)]


def _issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("issue_number", issue.get("number", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _labels(issue: dict[str, Any]) -> list[str]:
    raw = issue.get("labels", [])
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))
    return sorted({name.strip().lower() for name in names if name.strip()})


def _text(issue: dict[str, Any], labels: list[str]) -> str:
    return "\n".join(
        [
            str(issue.get("title", "")),
            str(issue.get("body", "")),
            " ".join(labels),
        ]
    ).lower()


def _automation_lane(
    issue: dict[str, Any],
    classified_issue: dict[str, Any],
    text: str,
    labels: list[str],
) -> str | None:
    classification = str(classified_issue.get("classification", ""))
    if classification == "workflow_governance":
        return "workflow_governance"
    if classification == "automation_health_gap":
        if "worker" in text:
            return "worker_alignment"
        return "automation_health"
    if classification == "generated_tracker" and "command-center" in labels:
        return "command_center"
    if classification == "security_followup" and (
        "security" in labels or "ghas" in labels or "autopilot" in text or "workflow" in text
    ):
        return "security_automation"
    return None


def _health_state(classified_issue: dict[str, Any], text: str) -> str:
    blocking_status = str(classified_issue.get("blocking_status", "review_required"))
    if blocking_status == "possible_blocker_needs_security_review":
        return "possible_blocker_review_required"
    if "findings: **0**" in text or "findings: 0" in text:
        return "healthy_observed"
    if "missing top-level permissions\n- none" in text:
        return "healthy_observed"
    if "unpinned reusable actions\n- none" in text:
        return "healthy_observed"
    if "present expected workflows: **14/14**" in text:
        return "healthy_observed"
    if "success" in text and "14d stale | link" in text:
        return "healthy_observed_with_required_review"
    if blocking_status.startswith("not_blocking"):
        return "not_blocking_context"
    return "review_required"


def _recommended_action(lane: str, health_state: str) -> str:
    if health_state == "possible_blocker_review_required":
        return "review_current_automation_or_security_evidence_before_closing"
    if health_state == "healthy_observed":
        return "retain_as_periodic_evidence_or_close_with_current_snapshot"
    if health_state == "healthy_observed_with_required_review":
        return "record_disposition_for_required_security_or_automation_followup"
    if lane == "command_center":
        return "keep_open_as_queue_control_center"
    if lane == "worker_alignment":
        return "convert_one_worker_alignment_gap_to_scoped_read_only_artifact_pr"
    if lane == "workflow_governance":
        return "verify workflow governance snapshot before remediation"
    return "human_review_required"


def build_automation_health(issues: list[dict[str, Any]]) -> dict[str, Any]:
    issue_queue_payload = classify_issues(issues)
    classified_by_number = {
        int(item["issue_number"]): item
        for item in issue_queue_payload["issues"]
        if isinstance(item.get("issue_number"), int)
    }

    signals: list[dict[str, Any]] = []
    for raw_issue in issues:
        number = _issue_number(raw_issue)
        classified_issue = classified_by_number.get(number, {})
        classification = str(classified_issue.get("classification", "needs_human_review"))
        if classification not in AUTOMATION_RELEVANT_CLASSES:
            continue

        labels = _labels(raw_issue)
        text = _text(raw_issue, labels)
        lane = _automation_lane(raw_issue, classified_issue, text, labels)
        if lane is None:
            continue

        health_state = _health_state(classified_issue, text)
        signals.append(
            {
                "issue_number": number,
                "title": str(raw_issue.get("title", "")),
                "lane": lane,
                "classification": classification,
                "health_state": health_state,
                "priority_score": int(classified_issue.get("priority_score", 0)),
                "blocking_status": str(classified_issue.get("blocking_status", "review_required")),
                "recommended_action": _recommended_action(lane, health_state),
                **AUTHORITY_BOUNDARY,
            }
        )

    signals.sort(key=lambda item: (-int(item["priority_score"]), int(item["issue_number"])))
    state_counts = Counter(str(item["health_state"]) for item in signals)
    lane_counts = Counter(str(item["lane"]) for item in signals)
    primary = next(
        (item for item in signals if item["health_state"] == "possible_blocker_review_required"),
        signals[0] if signals else None,
    )
    status = "healthy_observed"
    if state_counts.get("possible_blocker_review_required", 0):
        status = "review_required"
    elif state_counts.get("review_required", 0):
        status = "review_required"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_issue_count": len(issues),
        "automation_signal_count": len(signals),
        "automation_signals": signals,
        "lane_counts": dict(sorted(lane_counts.items())),
        "health_state_counts": dict(sorted(state_counts.items())),
        "primary_signal_issue": primary["issue_number"] if primary else None,
        "recommended_next_action": primary["recommended_action"] if primary else None,
        "input_issue_queue_schema_version": issue_queue_payload["schema_version"],
        **AUTHORITY_BOUNDARY,
    }


def automation_health_input_provenance(
    *,
    issues_json: str | Path,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generator_path: str | Path | None = None,
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    issues_path = Path(issues_json)
    issues = _load_issues(issues_path)
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    classifier_source = Path(issue_queue_report.__file__).resolve()
    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=generator.read_bytes(),
        data_inputs={
            "issues_json": issues_path.read_bytes(),
            "issue_queue_classifier_source": classifier_source.read_bytes(),
        },
        root=root,
        source_issue_numbers=extract_source_issue_numbers(issues),
        source_run_ids=collect_source_run_ids(source_run_ids, issues=issues),
        input_artifact_schemas={
            "issue_queue_classifier": issue_queue_report.SCHEMA_VERSION,
        },
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def check_automation_health_freshness(
    *,
    issues_json: str | Path,
    report_path: str | Path,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    current = automation_health_input_provenance(
        issues_json=issues_json,
        root=root,
        source_run_ids=source_run_ids,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )
    return check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )


def write_automation_health_artifact(
    *,
    issues_json: str | Path,
    out: str | Path = DEFAULT_OUT,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    issues = _load_issues(issues_json)
    payload = build_automation_health(issues)
    provenance = automation_health_input_provenance(
        issues_json=issues_json,
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
        prog="sdetkit automation-health",
        description="Build a read-only automation health artifact from issue snapshots.",
    )
    parser.add_argument("--issues-json", required=True)
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
        freshness = check_automation_health_freshness(
            issues_json=ns.issues_json,
            report_path=ns.out,
            root=ns.root,
            source_run_ids=ns.source_run_id,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_automation_health_artifact(
        issues_json=ns.issues_json,
        out=ns.out,
        root=ns.root,
        source_run_ids=ns.source_run_id,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"automation_health_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"automation_signals={payload['automation_signal_count']}\n")
        sys.stdout.write(f"primary_signal_issue={payload['primary_signal_issue']}\n")
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
