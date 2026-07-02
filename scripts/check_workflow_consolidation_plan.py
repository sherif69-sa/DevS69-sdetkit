#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PLAN_ID = "sdetkit.workflow-consolidation.v1"
REPORT_SCHEMA = "sdetkit.workflow-consolidation.parity-report.v1"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _workflow_name(value: str) -> str:
    prefix = ".github/workflows/"
    return value[len(prefix) :] if value.startswith(prefix) else value


def _disposition_groups(plan: dict[str, Any]) -> dict[str, list[str]]:
    bundles = plan.get("merge_bundles", {})
    bundle_items: list[str] = []
    if isinstance(bundles, dict):
        for name in sorted(bundles):
            bundle_items.extend(_strings(bundles[name]))
    return {
        "primary": _strings(plan.get("keep_primary")),
        "merge_bundle": bundle_items,
        "retirement_candidate": _strings(plan.get("candidate_retire_or_absorb")),
        "standalone_supporting": _strings(plan.get("standalone_supporting")),
    }


def evaluate_plan(
    topology: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    inventory = sorted(_workflow_name(item) for item in _strings(topology.get("inventory")))
    inventory_set = set(inventory)
    groups = _disposition_groups(plan)
    assigned = [item for values in groups.values() for item in values]
    assignment_counts = Counter(assigned)
    duplicates = sorted(item for item, count in assignment_counts.items() if count > 1)
    assigned_set = set(assigned)

    if plan.get("plan_id") != PLAN_ID:
        violations.append(
            {
                "code": "plan_id_mismatch",
                "expected": PLAN_ID,
                "actual": plan.get("plan_id"),
            }
        )

    declared_count = plan.get("current_workflow_count")
    if declared_count != len(inventory):
        violations.append(
            {
                "code": "workflow_count_drift",
                "declared": declared_count,
                "actual": len(inventory),
            }
        )

    missing = sorted(inventory_set - assigned_set)
    unknown = sorted(assigned_set - inventory_set)
    if missing or unknown:
        violations.append(
            {
                "code": "workflow_disposition_coverage_mismatch",
                "missing": missing,
                "unknown": unknown,
            }
        )
    if duplicates:
        violations.append(
            {
                "code": "workflow_disposition_overlap",
                "workflows": duplicates,
            }
        )

    primary = sorted(groups["primary"])
    topology_primary = sorted(_strings(topology.get("primary_anchors")))
    if primary != topology_primary:
        violations.append(
            {
                "code": "primary_anchor_drift",
                "plan": primary,
                "topology": topology_primary,
            }
        )

    target = plan.get("target_primary_workflow_count")
    topology_target = (topology.get("budgets") or {}).get("target_primary_workflow_count")
    if target != topology_target:
        violations.append(
            {
                "code": "primary_target_drift",
                "plan": target,
                "topology": topology_target,
            }
        )
    if not isinstance(target, int) or len(primary) > target:
        violations.append(
            {
                "code": "primary_workflow_budget_exceeded",
                "target": target,
                "actual": len(primary),
            }
        )

    metadata_lists = {
        "compatibility_bridges": _strings(plan.get("compatibility_bridges")),
        "reusable_workflows": _strings(plan.get("reusable_workflows")),
        "trusted_publishers": _strings(plan.get("trusted_publishers")),
    }
    for field, values in metadata_lists.items():
        invalid = sorted(set(values) - inventory_set)
        if invalid:
            violations.append(
                {
                    "code": "classification_references_unknown_workflow",
                    "field": field,
                    "workflows": invalid,
                }
            )

    zero_signal = plan.get("zero_signal_issue_policy", {})
    if not isinstance(zero_signal, dict):
        zero_signal = {}
    if zero_signal.get("create_issue_when_actionable_finding_count_is_zero") is not False:
        violations.append({"code": "zero_signal_issue_creation_not_prohibited"})
    first_enforced = str(zero_signal.get("first_enforced_workflow") or "").strip()
    if first_enforced not in inventory_set:
        violations.append(
            {
                "code": "zero_signal_policy_workflow_missing",
                "workflow": first_enforced,
            }
        )

    classifications: dict[str, dict[str, Any]] = {}
    for disposition, values in groups.items():
        for workflow in values:
            classifications[workflow] = {
                "disposition": disposition,
                "compatibility_bridge": workflow in metadata_lists["compatibility_bridges"],
                "reusable": workflow in metadata_lists["reusable_workflows"],
                "trusted_publisher": workflow in metadata_lists["trusted_publishers"],
            }

    return {
        "schema_version": REPORT_SCHEMA,
        "status": "passed" if not violations else "failed",
        "reporting_only": True,
        "repo_mutation": False,
        "metrics": {
            "workflow_count": len(inventory),
            "primary_workflow_count": len(groups["primary"]),
            "merge_bundle_workflow_count": len(groups["merge_bundle"]),
            "retirement_candidate_workflow_count": len(groups["retirement_candidate"]),
            "standalone_supporting_workflow_count": len(groups["standalone_supporting"]),
            "compatibility_bridge_workflow_count": len(metadata_lists["compatibility_bridges"]),
            "reusable_workflow_count": len(metadata_lists["reusable_workflows"]),
            "trusted_publisher_workflow_count": len(metadata_lists["trusted_publishers"]),
        },
        "classifications": dict(sorted(classifications.items())),
        "violations": violations,
        "authority_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "workflow_retirement_allowed": False,
            "merge_authorized": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Workflow consolidation parity report",
        "",
        f"- status: `{report['status']}`",
        f"- workflow_count: {report['metrics']['workflow_count']}",
        f"- primary_workflow_count: {report['metrics']['primary_workflow_count']}",
        f"- merge_bundle_workflow_count: {report['metrics']['merge_bundle_workflow_count']}",
        (
            "- retirement_candidate_workflow_count: "
            f"{report['metrics']['retirement_candidate_workflow_count']}"
        ),
        (
            "- standalone_supporting_workflow_count: "
            f"{report['metrics']['standalone_supporting_workflow_count']}"
        ),
        "- reporting_only: true",
        "- workflow_retirement_allowed: false",
        "",
        "## Violations",
        "",
    ]
    violations = report.get("violations", [])
    if violations:
        for violation in violations:
            lines.append(
                f"- `{violation.get('code', 'unknown')}`: `{json.dumps(violation, sort_keys=True)}`"
            )
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="check_workflow_consolidation_plan.py")
    parser.add_argument(
        "--topology-contract",
        default="docs/contracts/workflow-topology.v1.json",
    )
    parser.add_argument(
        "--consolidation-plan",
        default="docs/contracts/workflow-consolidation-plan.v1.json",
    )
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_plan(
        _read_json(Path(args.topology_contract)),
        _read_json(Path(args.consolidation_plan)),
    )
    if args.out_json:
        target = Path(args.out_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_md:
        target = Path(args.out_md)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_markdown(report), encoding="utf-8")

    print(f"status={report['status']}")
    for key, value in sorted(report["metrics"].items()):
        print(f"{key}={value}")
    print(f"violation_count={len(report['violations'])}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
