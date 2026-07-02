#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

REPORT_SCHEMA = "sdetkit.workflow-overlap-report.v1"

_PROOF_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python -m pre_commit", re.compile(r"(?:python\s+-m\s+)?pre[_-]commit\b")),
    ("pytest", re.compile(r"(?:python\s+-m\s+)?pytest\b")),
    ("bash quality.sh", re.compile(r"(?:bash\s+)?\.?/?quality\.sh\b")),
    ("python -m sdetkit gate fast", re.compile(r"python\s+-m\s+sdetkit\s+gate\s+fast\b")),
    (
        "python -m sdetkit gate release",
        re.compile(r"python\s+-m\s+sdetkit\s+gate\s+release\b"),
    ),
    ("python -m sdetkit doctor", re.compile(r"python\s+-m\s+sdetkit\s+doctor\b")),
    ("ruff check", re.compile(r"(?:python\s+-m\s+)?ruff\s+check\b")),
    ("ruff format", re.compile(r"(?:python\s+-m\s+)?ruff\s+format\b")),
    ("mypy", re.compile(r"(?:python\s+-m\s+)?mypy\b")),
    ("mkdocs build", re.compile(r"(?:python\s+-m\s+)?mkdocs\s+build\b")),
    ("python -m build", re.compile(r"python\s+-m\s+build\b")),
    ("twine check", re.compile(r"(?:python\s+-m\s+)?twine\s+check\b")),
    (
        "check-wheel-contents",
        re.compile(r"(?:python\s+-m\s+)?check[_-]wheel[_-]contents\b"),
    ),
    ("pip-audit", re.compile(r"(?:python\s+-m\s+)?pip[_-]audit\b")),
    ("osv-scanner", re.compile(r"\bosv-scanner\b")),
    ("trivy", re.compile(r"\btrivy\b")),
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [str(item).strip() for item in _list(value) if str(item).strip()]


def _load_workflow(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected YAML mapping in {path}")
    normalized = dict(payload)
    if True in normalized and "on" not in normalized:
        normalized["on"] = normalized.pop(True)
    return {str(key): value for key, value in normalized.items()}


def _triggers(workflow: Mapping[str, Any]) -> list[str]:
    raw = workflow.get("on", {})
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return sorted({str(item) for item in raw})
    if isinstance(raw, Mapping):
        return sorted(str(key) for key in raw)
    return []


def _permission_map(value: object) -> dict[str, str]:
    if isinstance(value, str):
        return {"*": value}
    return {str(key): str(item) for key, item in _mapping(value).items()}


def _permission_summary(workflow: Mapping[str, Any]) -> dict[str, Any]:
    top_level = _permission_map(workflow.get("permissions"))
    jobs: dict[str, dict[str, str]] = {}
    effective_write_scopes: set[str] = {
        key for key, value in top_level.items() if str(value).casefold() == "write"
    }
    for job_id, raw_job in sorted(_mapping(workflow.get("jobs")).items()):
        job_permissions = _permission_map(_mapping(raw_job).get("permissions"))
        if job_permissions:
            jobs[job_id] = job_permissions
            effective_write_scopes.update(
                key for key, value in job_permissions.items() if str(value).casefold() == "write"
            )
    return {
        "top_level": dict(sorted(top_level.items())),
        "jobs": jobs,
        "effective_write_scopes": sorted(effective_write_scopes),
    }


def _joined_shell_lines(run: str) -> list[str]:
    joined: list[str] = []
    buffer = ""
    for raw_line in run.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        buffer = f"{buffer} {line}".strip() if buffer else line
        if buffer.endswith("\\"):
            buffer = buffer[:-1].rstrip()
            continue
        joined.append(buffer)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _proof_signatures(run: str) -> list[str]:
    found: set[str] = set()
    for line in _joined_shell_lines(run):
        compact = re.sub(r"\s+", " ", line).strip()
        for name, pattern in _PROOF_PATTERNS:
            if pattern.search(compact):
                found.add(name)
    return sorted(found)


def _artifact_step(step: Mapping[str, Any]) -> dict[str, Any] | None:
    uses = str(step.get("uses") or "")
    if "actions/upload-artifact@" in uses:
        direction = "produces"
    elif "actions/download-artifact@" in uses:
        direction = "consumes"
    else:
        return None
    with_block = _mapping(step.get("with"))
    return {
        "direction": direction,
        "name": str(with_block.get("name") or "<dynamic-or-default>"),
        "path": str(with_block.get("path") or ""),
        "action": uses,
    }


def _job_records(
    workflow: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    proofs: set[str] = set()
    artifacts: list[dict[str, Any]] = []
    for job_id, raw_job in sorted(_mapping(workflow.get("jobs")).items()):
        job = _mapping(raw_job)
        status_name = str(job.get("name") or job_id)
        job_proofs: set[str] = set()
        job_artifacts: list[dict[str, Any]] = []
        actions: set[str] = set()
        for raw_step in _list(job.get("steps")):
            step = _mapping(raw_step)
            uses = str(step.get("uses") or "")
            if uses:
                actions.add(uses)
            run = str(step.get("run") or "")
            job_proofs.update(_proof_signatures(run))
            artifact = _artifact_step(step)
            if artifact is not None:
                artifact["job"] = job_id
                job_artifacts.append(artifact)
        proofs.update(job_proofs)
        artifacts.extend(job_artifacts)
        records.append(
            {
                "id": job_id,
                "status_name": status_name,
                "runs_on": job.get("runs-on", ""),
                "proof_commands": sorted(job_proofs),
                "actions": sorted(actions),
                "artifacts": job_artifacts,
            }
        )
    return records, sorted(proofs), artifacts


def _classification_map(plan: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for workflow in _strings(plan.get("keep_primary")):
        out[workflow] = "primary"
    for values in _mapping(plan.get("merge_bundles")).values():
        for workflow in _strings(values):
            out[workflow] = "merge_bundle"
    for workflow in _strings(plan.get("candidate_retire_or_absorb")):
        out[workflow] = "retirement_candidate"
    for workflow in _strings(plan.get("standalone_supporting")):
        out[workflow] = "standalone_supporting"
    return out


def _overlap_groups(
    index: Mapping[object, Iterable[str]], *, key_name: str
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for key, values in index.items():
        workflows = sorted(set(values))
        if len(workflows) < 2:
            continue
        groups.append({key_name: key, "workflow_count": len(workflows), "workflows": workflows})
    return sorted(groups, key=lambda item: (-int(item["workflow_count"]), str(item[key_name])))


def build_report(
    root: Path,
    *,
    topology_contract: Path,
    required_checks_contract: Path,
    consolidation_plan: Path,
) -> dict[str, Any]:
    topology = _read_json(topology_contract)
    required = _read_json(required_checks_contract)
    plan = _read_json(consolidation_plan)
    classifications = _classification_map(plan)
    violations: list[dict[str, Any]] = []
    workflows: list[dict[str, Any]] = []
    trigger_index: defaultdict[tuple[str, ...], list[str]] = defaultdict(list)
    proof_index: defaultdict[str, list[str]] = defaultdict(list)
    action_index: defaultdict[str, list[str]] = defaultdict(list)
    artifact_index: defaultdict[str, list[str]] = defaultdict(list)
    display_name_index: defaultdict[str, list[str]] = defaultdict(list)

    inventory = _strings(topology.get("inventory"))
    for relative in inventory:
        path = root / relative
        name = Path(relative).name
        if not path.is_file():
            violations.append({"code": "workflow_missing", "path": relative})
            continue
        try:
            workflow = _load_workflow(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            violations.append(
                {"code": "workflow_parse_failed", "path": relative, "error": str(exc)}
            )
            continue
        display_name = str(workflow.get("name") or Path(relative).stem)
        triggers = _triggers(workflow)
        jobs, proofs, artifacts = _job_records(workflow)
        permissions = _permission_summary(workflow)
        if name not in classifications:
            violations.append({"code": "workflow_unclassified", "workflow": name})
        record = {
            "path": relative,
            "workflow": name,
            "display_name": display_name,
            "disposition": classifications.get(name, "unknown"),
            "triggers": triggers,
            "permissions": permissions,
            "job_status_names": [job["status_name"] for job in jobs],
            "jobs": jobs,
            "proof_commands": proofs,
            "artifacts": artifacts,
        }
        workflows.append(record)
        trigger_index[tuple(triggers)].append(name)
        display_name_index[display_name.casefold()].append(name)
        for proof in proofs:
            proof_index[proof].append(name)
        for job in jobs:
            for action in job["actions"]:
                action_index[action.split("@", 1)[0]].append(name)
        for artifact in artifacts:
            artifact_index[str(artifact["name"])].append(name)

    required_contexts = _strings(required.get("contexts"))
    required_context_mapping: dict[str, list[str]] = {}
    for context in required_contexts:
        matches = sorted(display_name_index.get(context.casefold(), []))
        if not matches:
            matches = sorted(
                record["workflow"]
                for record in workflows
                if context.casefold()
                in {str(item).casefold() for item in record["job_status_names"]}
            )
        required_context_mapping[context] = matches
        if not matches:
            violations.append({"code": "required_context_unmapped", "context": context})

    proof_groups = _overlap_groups(proof_index, key_name="proof_command")
    trigger_groups = _overlap_groups(trigger_index, key_name="triggers")
    action_groups = _overlap_groups(action_index, key_name="action")
    artifact_groups = _overlap_groups(artifact_index, key_name="artifact_name")
    duplicate_workflow_memberships = sorted(
        {workflow for group in proof_groups for workflow in group["workflows"]}
    )
    proof_occurrences = Counter(proof for record in workflows for proof in record["proof_commands"])

    workflows.sort(key=lambda item: item["workflow"])
    return {
        "schema_version": REPORT_SCHEMA,
        "status": "passed" if not violations else "failed",
        "reporting_only": True,
        "source": {
            "topology_contract": topology_contract.relative_to(root).as_posix(),
            "required_checks_contract": required_checks_contract.relative_to(root).as_posix(),
            "consolidation_plan": consolidation_plan.relative_to(root).as_posix(),
        },
        "metrics": {
            "workflow_count": len(workflows),
            "required_context_count": len(required_contexts),
            "duplicate_trigger_group_count": len(trigger_groups),
            "duplicate_proof_command_group_count": len(proof_groups),
            "workflows_with_duplicate_proof_membership": len(duplicate_workflow_memberships),
            "duplicate_action_group_count": len(action_groups),
            "duplicate_artifact_name_group_count": len(artifact_groups),
            "workflow_with_write_permissions_count": sum(
                bool(record["permissions"]["effective_write_scopes"]) for record in workflows
            ),
        },
        "required_status_contexts": required_contexts,
        "required_context_mapping": required_context_mapping,
        "proof_command_occurrences": dict(sorted(proof_occurrences.items())),
        "overlaps": {
            "triggers": trigger_groups,
            "proof_commands": proof_groups,
            "actions": action_groups,
            "artifact_names": artifact_groups,
        },
        "workflows": workflows,
        "violations": violations,
        "authority_boundary": {
            "automation_allowed": False,
            "workflow_retirement_allowed": False,
            "required_check_rename_allowed": False,
            "permission_change_allowed": False,
            "merge_authorized": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    metrics = _mapping(report.get("metrics"))
    lines = [
        "# Workflow overlap inventory",
        "",
        f"- status: `{report.get('status')}`",
        f"- workflow_count: {metrics.get('workflow_count', 0)}",
        f"- duplicate_trigger_group_count: {metrics.get('duplicate_trigger_group_count', 0)}",
        (
            "- duplicate_proof_command_group_count: "
            f"{metrics.get('duplicate_proof_command_group_count', 0)}"
        ),
        (
            "- workflows_with_duplicate_proof_membership: "
            f"{metrics.get('workflows_with_duplicate_proof_membership', 0)}"
        ),
        f"- reporting_only: {str(report.get('reporting_only', False)).lower()}",
        "",
        "## Required status contexts",
        "",
    ]
    mapping = _mapping(report.get("required_context_mapping"))
    for context in _strings(report.get("required_status_contexts")):
        matches = ", ".join(_strings(mapping.get(context))) or "UNMAPPED"
        lines.append(f"- `{context}` -> {matches}")
    lines.extend(["", "## Repeated proof commands", ""])
    proof_groups = _mapping(report.get("overlaps")).get("proof_commands", [])
    if isinstance(proof_groups, list) and proof_groups:
        for group in proof_groups:
            item = _mapping(group)
            workflows = ", ".join(_strings(item.get("workflows")))
            lines.append(
                f"- `{item.get('proof_command')}` ({item.get('workflow_count')}): {workflows}"
            )
    else:
        lines.append("- none")
    lines.extend(
        ["", "## Safety boundary", "", "No workflow retirement is authorized by this report."]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_workflow_overlap_report.py")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--topology-contract",
        default="docs/contracts/workflow-topology.v1.json",
    )
    parser.add_argument(
        "--required-checks-contract",
        default="docs/contracts/required-checks.v1.json",
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
    root = Path(args.root).resolve()
    report = build_report(
        root,
        topology_contract=root / args.topology_contract,
        required_checks_contract=root / args.required_checks_contract,
        consolidation_plan=root / args.consolidation_plan,
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
    for key, value in sorted(_mapping(report["metrics"]).items()):
        print(f"{key}={value}")
    print(f"violation_count={len(_list(report['violations']))}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
