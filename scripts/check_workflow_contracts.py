#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

TOPOLOGY_SCHEMA = "devs69.workflow_topology.v1"
REQUIRED_CHECKS_SCHEMA = "devs69.required_checks.v1"
REPORT_SCHEMA = "devs69.workflow_contract_report.v1"

ACTION_LINE_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s*(?P<spec>[^\s#]+)(?:\s+#\s*(?P<comment>.*?))?\s*$",
    re.MULTILINE,
)
FULL_SHA_SPEC_RE = re.compile(r"^[^@\s]+@[0-9a-fA-F]{40}$")
EXACT_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?P<scope>"
    r"actions|attestations|checks|contents|deployments|id-token|issues|"
    r"packages|pages|pull-requests|security-events"
    r"):\s*write\s*(?:#.*)?$",
    re.MULTILINE,
)
WRITE_ALL_RE = re.compile(r"^\s*permissions:\s*write-all\s*(?:#.*)?$", re.MULTILINE)
WORKFLOW_CALL_RE = re.compile(r"^\s*workflow_call\s*:", re.MULTILINE)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def workflow_files(root: Path) -> list[Path]:
    workflow_root = root / ".github" / "workflows"
    return sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])


def _job_count(text: str) -> int:
    in_jobs = False
    count = 0
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not in_jobs:
            if stripped == "jobs:" and len(raw_line) - len(raw_line.lstrip()) == 0:
                in_jobs = True
            continue
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        if indent == 0:
            break
        if indent == 2 and re.fullmatch(r"[A-Za-z0-9_.-]+:", stripped):
            count += 1
    return count


def _action_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in ACTION_LINE_RE.finditer(text):
        spec = match.group("spec")
        if spec.startswith("./"):
            continue
        comment = (match.group("comment") or "").strip()
        rows.append(
            {
                "spec": spec,
                "pinned_full_sha": bool(FULL_SHA_SPEC_RE.fullmatch(spec)),
                "annotation": comment,
                "annotation_exact_semver": bool(EXACT_SEMVER_RE.fullmatch(comment)),
            }
        )
    return rows


def scan_workflow(root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    actions = _action_rows(text)
    write_scopes = sorted({match.group("scope") for match in WRITE_PERMISSION_RE.finditer(text)})
    if WRITE_ALL_RE.search(text):
        write_scopes.append("write-all")
    relative = path.relative_to(root).as_posix()
    job_count = _job_count(text)
    line_count = len(text.splitlines())
    reusable = bool(WORKFLOW_CALL_RE.search(text))
    heavy = line_count >= 250 or job_count >= 8
    monolithic = line_count >= 250 and job_count <= 2 and not reusable
    return {
        "path": relative,
        "line_count": line_count,
        "job_count": job_count,
        "reusable": reusable,
        "heavy": heavy,
        "monolithic": monolithic,
        "write_scopes": sorted(set(write_scopes)),
        "actions": actions,
        "unpinned_action_count": sum(not row["pinned_full_sha"] for row in actions),
        "metadata_debt_count": sum(not row["annotation_exact_semver"] for row in actions),
    }


def collect_repository(root: Path) -> dict[str, Any]:
    workflows = [scan_workflow(root, path) for path in workflow_files(root)]
    return {
        "workflows": workflows,
        "inventory": [item["path"] for item in workflows],
        "metrics": {
            "workflow_count": len(workflows),
            "write_permission_workflow_count": sum(
                bool(item["write_scopes"]) for item in workflows
            ),
            "reusable_workflow_count": sum(bool(item["reusable"]) for item in workflows),
            "heavy_workflow_count": sum(bool(item["heavy"]) for item in workflows),
            "monolithic_workflow_count": sum(bool(item["monolithic"]) for item in workflows),
            "unpinned_action_count": sum(item["unpinned_action_count"] for item in workflows),
            "metadata_drift_workflow_count": sum(
                item["metadata_debt_count"] > 0 for item in workflows
            ),
            "metadata_drift_occurrence_count": sum(
                item["metadata_debt_count"] for item in workflows
            ),
        },
    }


def build_topology_contract(
    root: Path,
    *,
    baseline_main_sha: str,
    primary_anchors: Sequence[str],
) -> dict[str, Any]:
    current = collect_repository(root)
    metrics = current["metrics"]
    return {
        "schema_version": TOPOLOGY_SCHEMA,
        "baseline_main_sha": baseline_main_sha,
        "inventory": current["inventory"],
        "primary_anchors": list(primary_anchors),
        "budgets": {
            "maximum_workflow_count": metrics["workflow_count"],
            "maximum_write_permission_workflow_count": metrics["write_permission_workflow_count"],
            "minimum_reusable_workflow_count": metrics["reusable_workflow_count"],
            "maximum_heavy_workflow_count": metrics["heavy_workflow_count"],
            "maximum_monolithic_workflow_count": metrics["monolithic_workflow_count"],
            "maximum_unpinned_action_count": 0,
            "maximum_metadata_drift_workflow_count": metrics["metadata_drift_workflow_count"],
            "maximum_metadata_drift_occurrence_count": metrics["metadata_drift_occurrence_count"],
            "target_primary_workflow_count": 12,
        },
        "policies": {
            "new_workflow_requires_contract_update": True,
            "workflow_retirement_requires_parity_evidence": True,
            "action_refs_require_full_sha": True,
            "action_annotations_target_exact_semver": True,
            "required_check_renames_require_compatibility_bridge": True,
            "permission_reduction_requires_human_review": True,
        },
        "authority_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def build_required_checks_contract(
    contexts: Sequence[str],
    *,
    baseline_main_sha: str,
) -> dict[str, Any]:
    normalized = sorted({str(item).strip() for item in contexts if str(item).strip()})
    return {
        "schema_version": REQUIRED_CHECKS_SCHEMA,
        "branch": "main",
        "baseline_main_sha": baseline_main_sha,
        "contexts": normalized,
        "compatibility": {
            "removal_requires_explicit_review": True,
            "rename_requires_bridge": True,
            "new_context_is_non_required_until_reviewed": True,
        },
        "authority_boundary": {
            "automation_allowed": False,
            "branch_protection_mutation_allowed": False,
            "merge_authorized": False,
        },
    }


def _normalize_live_contexts(payload: Any) -> list[str]:
    if isinstance(payload, list):
        return sorted({str(item).strip() for item in payload if str(item).strip()})
    if isinstance(payload, dict):
        contexts = payload.get("contexts", [])
        if isinstance(contexts, list):
            return sorted({str(item).strip() for item in contexts if str(item).strip()})
    raise ValueError("live required-context payload must be a list or an object with contexts")


def evaluate_contracts(
    root: Path,
    topology_contract: dict[str, Any],
    required_checks_contract: dict[str, Any],
    *,
    live_required_contexts: list[str] | None = None,
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    current = collect_repository(root)
    metrics = current["metrics"]

    if topology_contract.get("schema_version") != TOPOLOGY_SCHEMA:
        violations.append({"code": "topology_schema_mismatch"})
    if required_checks_contract.get("schema_version") != REQUIRED_CHECKS_SCHEMA:
        violations.append({"code": "required_checks_schema_mismatch"})

    expected_inventory = topology_contract.get("inventory", [])
    if not isinstance(expected_inventory, list):
        expected_inventory = []
    expected_inventory = sorted(str(item) for item in expected_inventory)
    if current["inventory"] != expected_inventory:
        violations.append(
            {
                "code": "workflow_inventory_mismatch",
                "expected": expected_inventory,
                "actual": current["inventory"],
                "added": sorted(set(current["inventory"]) - set(expected_inventory)),
                "removed": sorted(set(expected_inventory) - set(current["inventory"])),
            }
        )

    anchors = topology_contract.get("primary_anchors", [])
    if not isinstance(anchors, list):
        anchors = []
    missing_anchors = sorted(
        anchor
        for anchor in (str(item) for item in anchors)
        if f".github/workflows/{anchor}" not in current["inventory"]
    )
    if missing_anchors:
        violations.append({"code": "primary_anchor_missing", "anchors": missing_anchors})

    budgets = topology_contract.get("budgets", {})
    if not isinstance(budgets, dict):
        budgets = {}

    maximum_checks = {
        "workflow_count": "maximum_workflow_count",
        "write_permission_workflow_count": "maximum_write_permission_workflow_count",
        "heavy_workflow_count": "maximum_heavy_workflow_count",
        "monolithic_workflow_count": "maximum_monolithic_workflow_count",
        "unpinned_action_count": "maximum_unpinned_action_count",
        "metadata_drift_workflow_count": "maximum_metadata_drift_workflow_count",
        "metadata_drift_occurrence_count": "maximum_metadata_drift_occurrence_count",
    }
    for metric, budget_key in maximum_checks.items():
        maximum = budgets.get(budget_key)
        if not isinstance(maximum, int):
            violations.append({"code": "budget_missing", "budget": budget_key})
            continue
        if int(metrics[metric]) > maximum:
            violations.append(
                {
                    "code": "budget_regression",
                    "metric": metric,
                    "maximum": maximum,
                    "actual": metrics[metric],
                }
            )

    minimum_reusable = budgets.get("minimum_reusable_workflow_count")
    if not isinstance(minimum_reusable, int):
        violations.append({"code": "budget_missing", "budget": "minimum_reusable_workflow_count"})
    elif metrics["reusable_workflow_count"] < minimum_reusable:
        violations.append(
            {
                "code": "budget_regression",
                "metric": "reusable_workflow_count",
                "minimum": minimum_reusable,
                "actual": metrics["reusable_workflow_count"],
            }
        )

    unpinned = [
        {"workflow": item["path"], "spec": row["spec"]}
        for item in current["workflows"]
        for row in item["actions"]
        if not row["pinned_full_sha"]
    ]
    if unpinned:
        violations.append({"code": "unpinned_actions", "actions": unpinned})

    contexts = required_checks_contract.get("contexts", [])
    if not isinstance(contexts, list):
        contexts = []
    normalized_contexts = [str(item).strip() for item in contexts if str(item).strip()]
    if normalized_contexts != sorted(set(normalized_contexts)):
        violations.append({"code": "required_contexts_not_sorted_unique"})
    if live_required_contexts is not None:
        if normalized_contexts != sorted(set(live_required_contexts)):
            violations.append(
                {
                    "code": "required_context_drift",
                    "contract": normalized_contexts,
                    "live": sorted(set(live_required_contexts)),
                }
            )

    ci_text = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    if "name: Workflow contracts" not in ci_text:
        violations.append({"code": "workflow_contract_job_missing"})
    if "python scripts/check_workflow_contracts.py" not in ci_text:
        violations.append({"code": "workflow_contract_command_missing"})

    return {
        "schema_version": REPORT_SCHEMA,
        "status": "passed" if not violations else "failed",
        "reporting_only": True,
        "repo_mutation": False,
        "metrics": metrics,
        "required_contexts": normalized_contexts,
        "violations": violations,
        "authority_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Workflow contract report",
        "",
        f"- status: `{report['status']}`",
        f"- workflow_count: {report['metrics']['workflow_count']}",
        (
            "- write_permission_workflow_count: "
            f"{report['metrics']['write_permission_workflow_count']}"
        ),
        f"- reusable_workflow_count: {report['metrics']['reusable_workflow_count']}",
        f"- unpinned_action_count: {report['metrics']['unpinned_action_count']}",
        (f"- metadata_drift_workflow_count: {report['metrics']['metadata_drift_workflow_count']}"),
        "- reporting_only: true",
        "- repo_mutation: false",
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
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="check_workflow_contracts.py")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--topology-contract",
        default="docs/contracts/workflow-topology.v1.json",
    )
    parser.add_argument(
        "--required-checks-contract",
        default="docs/contracts/required-checks.v1.json",
    )
    parser.add_argument("--live-required-contexts-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    topology = _read_json(Path(args.topology_contract))
    required = _read_json(Path(args.required_checks_contract))
    live: list[str] | None = None
    if args.live_required_contexts_json:
        live_payload = json.loads(
            Path(args.live_required_contexts_json).read_text(encoding="utf-8")
        )
        live = _normalize_live_contexts(live_payload)

    report = evaluate_contracts(
        root,
        topology,
        required,
        live_required_contexts=live,
    )
    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(report) + "\n", encoding="utf-8")

    print(f"status={report['status']}")
    for key, value in sorted(report["metrics"].items()):
        print(f"{key}={value}")
    print(f"violation_count={len(report['violations'])}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
