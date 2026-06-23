from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    collect_source_run_ids,
    extract_source_issue_numbers,
    render_freshness_text,
)

SCHEMA_VERSION = "sdetkit.issue_queue_classifier.v2"
DEFAULT_OUT = "build/sdetkit/issue-queue-classifier.json"
GENERATOR_SOURCE = "src/sdetkit/issue_queue_classifier.py"

CLASSIFICATIONS = {
    "real_blocker",
    "product_roadmap_gap",
    "generated_tracker",
    "security_followup",
    "workflow_governance",
    "dependency_hygiene",
    "release_readiness",
    "docs_operator_gap",
    "adoption_surface_gap",
    "automation_health_gap",
    "stale_or_superseded",
    "needs_human_review",
}

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _label_names(raw_labels: object) -> list[str]:
    if not isinstance(raw_labels, list):
        return []
    names: list[str] = []
    for item in raw_labels:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))
    return sorted({name.strip().lower() for name in names if name.strip()})


def _issue_number(issue: dict[str, Any]) -> int:
    value = issue.get("issue_number", issue.get("number", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _issue_text(issue: dict[str, Any], labels: list[str]) -> str:
    parts = [
        str(issue.get("title", "")),
        str(issue.get("body", "")),
        " ".join(labels),
    ]
    return "\n".join(parts).lower()


def classify_issue(issue: dict[str, Any]) -> dict[str, Any]:
    labels = _label_names(issue.get("labels"))
    text = _issue_text(issue, labels)

    if "stale" in labels or "superseded" in text:
        classification = "stale_or_superseded"
    elif "command-center" in labels or "command center" in text:
        classification = "generated_tracker"
    elif "security" in labels or "ghas" in labels or "security" in text or "ghas" in text:
        classification = "security_followup"
    elif "workflow governance" in text or "workflow_permission" in text:
        classification = "workflow_governance"
    elif "automation" in labels or "worker" in text or "automation" in text:
        classification = "automation_health_gap"
    elif "documentation" in labels or "docs" in text or "orphan docs" in text:
        classification = "docs_operator_gap"
    elif "dependency" in labels or "deps" in text:
        classification = "dependency_hygiene"
    elif "release" in labels or "release" in text:
        classification = "release_readiness"
    elif "adoption" in labels or "adoption" in text:
        classification = "adoption_surface_gap"
    elif "enhancement" in labels or "optimization" in text or "roadmap" in text:
        classification = "product_roadmap_gap"
    elif "blocker" in labels or "p0" in labels:
        classification = "real_blocker"
    else:
        classification = "needs_human_review"

    priority_score = _priority_score(classification, labels, text)
    recommended_action = _recommended_action(classification, text)
    proof_required = classification not in {"generated_tracker", "stale_or_superseded"}
    blocking_status = _blocking_status(classification, text)

    return {
        "issue_number": _issue_number(issue),
        "title": str(issue.get("title", "")),
        "state": str(issue.get("state", "open")),
        "labels": labels,
        "created_at": str(issue.get("created_at", issue.get("createdAt", ""))),
        "updated_at": str(issue.get("updated_at", issue.get("updatedAt", ""))),
        "classification": classification,
        "priority_score": priority_score,
        "roadmap_alignment": _roadmap_alignment(classification),
        "blocking_status": blocking_status,
        "recommended_action": recommended_action,
        "proof_required_before_close": proof_required,
        "linked_pr_or_none": _linked_pr_or_none(issue),
        **AUTHORITY_BOUNDARY,
    }


def _priority_score(classification: str, labels: list[str], text: str) -> int:
    score = 0
    if "priority:high" in labels:
        score += 450
    elif "priority:medium" in labels:
        score += 200
    elif "priority:low" in labels:
        score += 100

    if classification == "real_blocker":
        score += 700
    elif classification == "security_followup":
        score += 300
    elif classification in {"workflow_governance", "automation_health_gap"}:
        score += 220
    elif classification in {"docs_operator_gap", "product_roadmap_gap"}:
        score += 160
    elif classification == "generated_tracker":
        score += 40

    if re.search(r"actionable findings:\s*[1-9]", text):
        score += 500
    if "findings: **0**" in text or "findings: 0" in text:
        score -= 120

    return max(score, 0)


def _blocking_status(classification: str, text: str) -> str:
    if classification == "real_blocker":
        return "blocking_until_proven_resolved"
    if classification == "security_followup" and re.search(r"actionable findings:\s*[1-9]", text):
        return "possible_blocker_needs_security_review"
    if classification == "generated_tracker":
        return "not_blocking_generated_tracker"
    if classification == "stale_or_superseded":
        return "not_blocking_if_current_evidence_confirms_superseded"
    return "review_required"


def _roadmap_alignment(classification: str) -> str:
    alignment = {
        "real_blocker": "green-main protection",
        "product_roadmap_gap": "roadmap lane selection",
        "generated_tracker": "maintenance queue hygiene",
        "security_followup": "security posture",
        "workflow_governance": "automation integrity",
        "dependency_hygiene": "dependency hygiene",
        "release_readiness": "release readiness",
        "docs_operator_gap": "operator docs experience",
        "adoption_surface_gap": "multi-repo adoption intelligence",
        "automation_health_gap": "automation integrity",
        "stale_or_superseded": "queue hygiene",
        "needs_human_review": "manual triage",
    }
    return alignment[classification]


def _recommended_action(classification: str, text: str) -> str:
    if classification == "generated_tracker":
        if "command center" in text:
            return "keep_open_as_command_center"
        return "use_as_input_not_as_the_whole_roadmap"
    if classification == "security_followup":
        return "review_current_security_evidence_then_open_scoped_fix_or_disposition_pr"
    if classification == "workflow_governance":
        return "close_only_after_current_workflow_evidence_or_scoped_governance_fix"
    if classification == "automation_health_gap":
        return "convert_to_read_only_automation_health_follow_up"
    if classification == "docs_operator_gap":
        return "link_or_defer_docs_gaps_with_focused_docs_pr"
    if classification == "product_roadmap_gap":
        return "convert_one_high_value_gap_to_scoped_pr_card"
    if classification == "dependency_hygiene":
        return "triage_dependency_truth_surfaces_before_fixing"
    if classification == "release_readiness":
        return "run_release_readiness_proof_before_closing"
    if classification == "adoption_surface_gap":
        return "scope_next_adoption_surface_pr_with_artifact_proof"
    if classification == "stale_or_superseded":
        return "close_only_after_current_evidence_confirms_superseded"
    if classification == "real_blocker":
        return "stop_feature_work_and_restore_green_baseline"
    return "human_review_required"


def _linked_pr_or_none(issue: dict[str, Any]) -> int | None:
    value = issue.get("linked_pr_or_none")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_issues(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_issues = payload
    elif isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        raw_issues = payload["issues"]
    else:
        raise ValueError("issues JSON must be a list or an object with an issues list")
    return [item for item in raw_issues if isinstance(item, dict)]


def classify_issues(issues: list[dict[str, Any]]) -> dict[str, Any]:
    classified = [classify_issue(issue) for issue in issues]
    classified.sort(key=lambda item: (-int(item["priority_score"]), int(item["issue_number"])))
    counts = Counter(str(item["classification"]) for item in classified)
    recommended = next(
        (
            item
            for item in classified
            if item["classification"] not in {"generated_tracker", "stale_or_superseded"}
        ),
        None,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_issue_count": len(issues),
        "issues": classified,
        "classification_counts": dict(sorted(counts.items())),
        "recommended_next_issue": recommended["issue_number"] if recommended else None,
        "recommended_next_action": recommended["recommended_action"] if recommended else None,
        **AUTHORITY_BOUNDARY,
    }


def issue_queue_input_provenance(
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
    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=generator.read_bytes(),
        data_inputs={"issues_json": issues_path.read_bytes()},
        root=root,
        source_issue_numbers=extract_source_issue_numbers(issues),
        source_run_ids=collect_source_run_ids(source_run_ids, issues=issues),
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def check_issue_queue_classifier_freshness(
    *,
    issues_json: str | Path,
    report_path: str | Path,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    current = issue_queue_input_provenance(
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


def write_issue_queue_classifier_artifact(
    *,
    issues_json: str | Path,
    out: str | Path = DEFAULT_OUT,
    root: str | Path = ".",
    source_run_ids: Sequence[int] = (),
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    issues = _load_issues(issues_json)
    payload = classify_issues(issues)
    provenance = issue_queue_input_provenance(
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
        prog="sdetkit issue-queue-classifier",
        description="Classify GitHub issue queue snapshots without mutating issues.",
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
        freshness = check_issue_queue_classifier_freshness(
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

    payload = write_issue_queue_classifier_artifact(
        issues_json=ns.issues_json,
        out=ns.out,
        root=ns.root,
        source_run_ids=ns.source_run_id,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"issue_queue_classifier_json={ns.out}\n")
        sys.stdout.write(f"issues_seen={payload['source_issue_count']}\n")
        sys.stdout.write(f"recommended_next_issue={payload['recommended_next_issue']}\n")
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
