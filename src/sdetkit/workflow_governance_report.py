from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.workflow_governance_report.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

FULL_SHA_RE = re.compile(r"^[a-fA-F0-9]{40}$")
USES_RE = re.compile(r"uses:\s*([^@\s#]+)@([^\s#]+)")


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _workflow_files(repo_root: Path) -> list[Path]:
    workflow_root = repo_root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return []
    return sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")])


def _line_contains_any(line: str, needles: Sequence[str]) -> bool:
    lower = line.lower()
    return any(needle in lower for needle in needles)


def _pip_install_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if _line_contains_any(line, ["pip install", "python -m pip install"])
    ]


def _uses_constraints(line: str) -> bool:
    return "-c constraints-ci.txt" in line or "--constraint constraints-ci.txt" in line


def _permissions_least_privilege(text: str) -> bool:
    lower = text.lower()
    if "permissions:" not in lower:
        return False
    banned = (
        "write-all",
        "contents: write",
        "actions: write",
        "checks: write",
        "pull-requests: write",
        "security-events: write",
        "id-token: write",
    )
    return not any(item in lower for item in banned)


def _local_equivalent_documented(text: str) -> bool:
    lower = text.lower()
    return (
        "local equivalent" in lower
        or "local proof" in lower
        or "make proof-after-format" in lower
        or "python -m pytest" in lower
    )


def _action_refs(text: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = USES_RE.search(line)
        if not match:
            continue
        action = match.group(1).strip()
        ref = match.group(2).strip()
        refs.append(
            {
                "line": line_number,
                "action": action,
                "ref": ref,
                "pinned_to_full_sha": bool(FULL_SHA_RE.fullmatch(ref)),
            }
        )
    return refs


def _workflow_findings(
    *, checklist: dict[str, str], action_refs: list[dict[str, Any]]
) -> list[str]:
    findings: list[str] = []
    for key, value in checklist.items():
        if value == "no":
            findings.append(key)

    if any(not bool(item["pinned_to_full_sha"]) for item in action_refs):
        findings.append("actions_pinned_to_sha")

    return sorted(set(findings))


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _yes_no_na(value: bool | None) -> str:
    if value is None:
        return "not_applicable"
    return _yes_no(value)


def analyze_workflow(repo_root: str | Path, workflow_path: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = Path(workflow_path)
    if not path.is_absolute():
        path = (root / path).resolve()

    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    action_refs = _action_refs(text)

    pip_lines = _pip_install_lines(text)
    install_uses_constraints: bool | None
    if pip_lines:
        install_uses_constraints = all(_uses_constraints(line) for line in pip_lines)
    else:
        install_uses_constraints = None

    upload_artifact_used = "actions/upload-artifact" in lower
    artifact_retention = None if not upload_artifact_used else "retention-days:" in lower

    actions_cache_used = "actions/cache" in lower
    setup_python_cache_used = "setup-python" in lower and "cache:" in lower
    setup_python_cache_has_dependency_path = (
        setup_python_cache_used and "cache-dependency-path:" in lower
    )
    explicit_cache_key_appropriate = "key:" in lower and (
        "hashfiles(" in lower or "github.sha" in lower
    )
    if not actions_cache_used and not setup_python_cache_used:
        cache_key_appropriate = None
    elif actions_cache_used and not explicit_cache_key_appropriate:
        cache_key_appropriate = False
    elif setup_python_cache_used and not setup_python_cache_has_dependency_path:
        cache_key_appropriate = False
    else:
        cache_key_appropriate = True

    mkdocs_used = "mkdocs build" in lower
    docs_build_strict = None if not mkdocs_used else "--strict" in lower

    checklist = {
        "permissions_least_privilege": _yes_no(_permissions_least_privilege(text)),
        "actions_pinned_to_sha": _yes_no(
            bool(action_refs) and all(bool(item["pinned_to_full_sha"]) for item in action_refs)
        ),
        "install_uses_constraints": _yes_no_na(install_uses_constraints),
        "cache_key_appropriate": _yes_no_na(cache_key_appropriate),
        "job_names_unique": "manual_review",
        "artifacts_have_retention": _yes_no_na(artifact_retention),
        "docs_build_strict": _yes_no_na(docs_build_strict),
        "no_secrets_in_pull_request_from_fork": "manual_review",
        "local_equivalent_command_documented": _yes_no(_local_equivalent_documented(text)),
    }

    findings = _workflow_findings(checklist=checklist, action_refs=action_refs)

    return {
        "path": _rel(root, path),
        "status": "passed" if not findings else "review_required",
        "checklist": checklist,
        "action_refs": action_refs,
        "findings": findings,
        "pip_install_lines": pip_lines,
        "upload_artifact_used": upload_artifact_used,
        "mkdocs_build_used": mkdocs_used,
        "review_first": True,
        "safe_to_patch": False,
    }


FINDING_GUIDANCE: dict[str, dict[str, str]] = {
    "permissions_least_privilege": {
        "priority": "P1",
        "product_reason": "Permission-scope findings affect workflow trust boundaries and operator confidence.",
        "recommended_change_type": "workflow_permission_review",
    },
    "artifacts_have_retention": {
        "priority": "P1",
        "product_reason": "Artifact retention controls whether operator evidence remains inspectable after CI completes.",
        "recommended_change_type": "artifact_retention_followup",
    },
    "install_uses_constraints": {
        "priority": "P2",
        "product_reason": "Constrained installs improve reproducibility of workflow proof lanes.",
        "recommended_change_type": "dependency_install_reproducibility",
    },
    "local_equivalent_command_documented": {
        "priority": "P2",
        "product_reason": "Local equivalents let operators reproduce workflow evidence without depending on GitHub Actions.",
        "recommended_change_type": "operator_reproducibility_docs",
    },
    "cache_key_appropriate": {
        "priority": "P2",
        "product_reason": "Cache-key quality protects CI determinism and avoids stale proof artifacts.",
        "recommended_change_type": "cache_review",
    },
    "docs_build_strict": {
        "priority": "P2",
        "product_reason": "Strict docs builds protect operator-facing documentation quality.",
        "recommended_change_type": "docs_quality_followup",
    },
    "actions_pinned_to_sha": {
        "priority": "P1",
        "product_reason": "Pinned actions protect supply-chain integrity for workflow execution.",
        "recommended_change_type": "action_pin_followup",
    },
}


def _priority_rank(priority: str) -> int:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return order.get(priority, 9)


def _workflow_paths_for_finding(workflows: list[dict[str, Any]], finding: str) -> list[str]:
    paths: list[str] = []
    for workflow in workflows:
        findings = workflow.get("findings")
        if isinstance(findings, list) and finding in findings:
            paths.append(str(workflow.get("path", "unknown")))
    return sorted(paths)


def _ranked_followups(
    *,
    finding_counts: dict[str, int],
    workflows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    followups: list[dict[str, Any]] = []
    for finding, count in finding_counts.items():
        guidance = FINDING_GUIDANCE.get(
            finding,
            {
                "priority": "P3",
                "product_reason": "Workflow governance finding requires operator review.",
                "recommended_change_type": "workflow_governance_followup",
            },
        )
        affected_workflows = _workflow_paths_for_finding(workflows, finding)
        followups.append(
            {
                "finding": finding,
                "priority": guidance["priority"],
                "affected_workflow_count": count,
                "sample_workflows": affected_workflows[:8],
                "product_reason": guidance["product_reason"],
                "recommended_change_type": guidance["recommended_change_type"],
                "review_first": True,
                "safe_to_patch": False,
            }
        )

    return sorted(
        followups,
        key=lambda item: (
            _priority_rank(str(item["priority"])),
            -int(item["affected_workflow_count"]),
            str(item["finding"]),
        ),
    )


def _actionability_summary(
    *,
    workflow_count: int,
    review_required_count: int,
    finding_count: int,
    ranked_followups: list[dict[str, Any]],
) -> dict[str, Any]:
    top_followup = ranked_followups[0] if ranked_followups else {}
    return {
        "workflow_count": workflow_count,
        "review_required_count": review_required_count,
        "finding_count": finding_count,
        "ranked_followup_count": len(ranked_followups),
        "top_followup": top_followup.get("finding", ""),
        "top_followup_priority": top_followup.get("priority", ""),
        "review_first": True,
        "safe_to_patch": False,
    }


def build_workflow_governance_report(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    workflows = [analyze_workflow(root, path) for path in _workflow_files(root)]
    review_required = [item for item in workflows if item["status"] == "review_required"]

    if not workflows:
        report_status = "no_workflows"
    elif review_required:
        report_status = "review_required"
    else:
        report_status = "passed"

    finding_counts: dict[str, int] = {}
    for workflow in workflows:
        for finding in workflow["findings"]:
            finding_counts[finding] = finding_counts.get(finding, 0) + 1

    sorted_finding_counts = dict(sorted(finding_counts.items()))
    finding_count = sum(sorted_finding_counts.values())
    ranked_followups = _ranked_followups(
        finding_counts=sorted_finding_counts,
        workflows=workflows,
    )
    actionability_summary = _actionability_summary(
        workflow_count=len(workflows),
        review_required_count=len(review_required),
        finding_count=finding_count,
        ranked_followups=ranked_followups,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": report_status,
        "repo_root": root.as_posix(),
        "workflow_count": len(workflows),
        "review_required_count": len(review_required),
        "finding_count": finding_count,
        "finding_counts": sorted_finding_counts,
        "ranked_followups": ranked_followups,
        "actionability_summary": actionability_summary,
        "workflows": workflows,
        "operator_summary": {
            "status": "workflow_governance_report_generated",
            "next_action": (
                "Review ranked workflow governance followups before making narrow CI hardening PRs."
                if review_required
                else "No workflow governance findings detected."
            ),
            "top_followup": actionability_summary["top_followup"],
            "ranked_followup_count": actionability_summary["ranked_followup_count"],
            "review_first": True,
            "safe_to_patch": False,
        },
        "rules": {
            "advisory_only": True,
            "workflow_mutation": False,
            "permissions_weakened": False,
            "checks_skipped": False,
            "required_checks_bypassed": False,
            "secrets_read": False,
            "review_first": True,
        },
        "advisory_only": True,
        "repo_mutation": False,
        "review_first": True,
        "safe_to_patch": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_workflow_governance_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit workflow governance report",
        "",
        f"- report_status: {payload['report_status']}",
        f"- workflow_count: {payload['workflow_count']}",
        f"- review_required_count: {payload['review_required_count']}",
        f"- finding_count: {payload.get('finding_count', 0)}",
        "- advisory_only: true",
        "- workflow_mutation: false",
        "- review_first: true",
        "",
        "## Finding counts",
        "",
    ]

    finding_counts = payload.get("finding_counts")
    if isinstance(finding_counts, dict) and finding_counts:
        for name, count in sorted(finding_counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Ranked follow-up candidates", ""])
    ranked_followups = payload.get("ranked_followups")
    if isinstance(ranked_followups, list) and ranked_followups:
        for index, followup in enumerate(ranked_followups, start=1):
            if not isinstance(followup, dict):
                continue
            lines.append(f"{index}. `{followup.get('finding', 'unknown')}`")
            lines.append(f"   - priority: `{followup.get('priority', 'P3')}`")
            lines.append(
                f"   - affected_workflow_count: {followup.get('affected_workflow_count', 0)}"
            )
            lines.append(
                f"   - recommended_change_type: `{followup.get('recommended_change_type', 'workflow_governance_followup')}`"
            )
            lines.append(
                f"   - review_first: {str(bool(followup.get('review_first', True))).lower()}"
            )
            lines.append(
                f"   - safe_to_patch: {str(bool(followup.get('safe_to_patch', False))).lower()}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Workflows", ""])
    workflows = payload.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        lines.append("- none")
    else:
        for workflow in workflows:
            if not isinstance(workflow, dict):
                continue
            lines.append(f"### {workflow.get('path', 'unknown')}")
            lines.append("")
            lines.append(f"- status: {workflow.get('status', 'unknown')}")
            lines.append(f"- review_first: {str(bool(workflow.get('review_first', True))).lower()}")
            lines.append(
                f"- safe_to_patch: {str(bool(workflow.get('safe_to_patch', False))).lower()}"
            )
            findings = workflow.get("findings")
            if isinstance(findings, list) and findings:
                lines.append("- findings: " + ", ".join(f"`{item}`" for item in findings))
            else:
                lines.append("- findings: none")
            checklist = workflow.get("checklist")
            if isinstance(checklist, dict):
                lines.append("- checklist:")
                for key, value in sorted(checklist.items()):
                    lines.append(f"  - {key}: `{value}`")
            lines.append("")

    lines.extend(
        [
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_workflow_governance_report(
    *,
    repo_root: str | Path,
    out: str | Path,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    payload = build_workflow_governance_report(repo_root=repo_root)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_workflow_governance_markdown(payload) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit workflow-governance-report",
        description="Build a read-only advisory governance report for GitHub Actions workflows.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="build/sdetkit/workflow-governance-report.json")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_workflow_governance_report(
        repo_root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_workflow_governance_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
