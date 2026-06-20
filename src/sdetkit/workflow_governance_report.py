from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.workflow_governance_report.v1"
WORKFLOW_PERMISSION_REVIEW_EVIDENCE_SCHEMA_VERSION = (
    "sdetkit.workflow_permission_review_evidence.v1"
)

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


PERMISSION_SCOPE_REASONS: dict[str, str] = {
    "contents: write": "May be required for commits, tags, releases, generated branches, or auto-update PR branches.",
    "pull-requests: write": "May be required for PR comments, reviews, labels, auto-merge, or PR creation/update flows.",
    "issues: write": "May be required for issue comments, tracker creation, maintenance reports, or issue updates.",
    "security-events: write": "May be required to upload SARIF or code-scanning/security findings.",
    "pages: write": "May be required by GitHub Pages deployment workflows.",
    "id-token: write": "May be required for OIDC, trusted publishing, attestations, or Pages deployment.",
    "attestations: write": "May be required for release provenance or build attestations.",
    "actions: write": "May be required only for workflow-dispatch/rerun/cancel operations and needs strict review.",
}


def _workflow_text_for_permission_review(repo_root: Path, workflow: dict[str, Any]) -> str:
    workflow_path = workflow.get("path")
    if not isinstance(workflow_path, str):
        return ""
    path = repo_root / workflow_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _granted_write_scopes(workflow_text: str) -> list[str]:
    scopes: list[str] = []
    for scope in PERMISSION_SCOPE_REASONS:
        if scope in workflow_text:
            scopes.append(scope)
    return sorted(scopes)


def _inferred_permission_reasons(workflow_text: str) -> list[str]:
    reasons: list[str] = []
    lower = workflow_text.lower()
    gh_api_issue_comment = "gh api" in lower and (
        "/issues/comments/" in lower or ("/issues/" in lower and "/comments" in lower)
    )

    if (
        "actions/github-script" in workflow_text
        or "gh pr comment" in workflow_text
        or gh_api_issue_comment
    ):
        reasons.append("GitHub API or gh-based PR/issue interaction detected.")
    if "issues.create" in workflow_text or "issues.update" in workflow_text:
        reasons.append("Issue create/update API usage detected.")
    if (
        "issues.createComment" in workflow_text
        or "pulls.createReview" in workflow_text
        or gh_api_issue_comment
    ):
        reasons.append("PR or issue comment/review API usage detected.")
    if "upload-sarif" in workflow_text or "security-events: write" in workflow_text:
        reasons.append("SARIF/code-scanning upload surface detected.")
    if "github-pages" in workflow_text or "pages: write" in workflow_text:
        reasons.append("GitHub Pages deployment surface detected.")
    if "attest" in workflow_text.lower() or "attestations: write" in workflow_text:
        reasons.append("Release attestation/provenance surface detected.")
    if "id-token: write" in workflow_text:
        reasons.append("OIDC token permission detected; requires environment/provider review.")
    if "contents: write" in workflow_text and (
        "peter-evans/create-pull-request" in workflow_text
        or "gh pr create" in workflow_text
        or "git push" in workflow_text
        or "auto-merge" in workflow_text
        or "release" in workflow_text.lower()
    ):
        reasons.append("Repository write/release/PR branch mutation surface detected.")

    return sorted(set(reasons))


def _permission_review_entry(repo_root: Path, workflow: dict[str, Any]) -> dict[str, Any]:
    workflow_text = _workflow_text_for_permission_review(repo_root, workflow)
    granted = _granted_write_scopes(workflow_text)
    reasons = _inferred_permission_reasons(workflow_text)

    return {
        "path": workflow.get("path", "unknown"),
        "has_permission_finding": "permissions_least_privilege" in workflow.get("findings", []),
        "granted_write_scopes": granted,
        "granted_write_scope_count": len(granted),
        "inferred_permission_reasons": reasons,
        "requires_human_review": True,
        "safe_to_patch": False,
        "recommended_change_type": "permission_reason_review",
    }


def _permission_review_kind(entry: dict[str, Any]) -> str:
    scopes = set(entry.get("granted_write_scopes", []))
    reasons = " ".join(str(reason) for reason in entry.get("inferred_permission_reasons", []))

    if (
        "attestations: write" in scopes
        or "id-token: write" in scopes
        and "release" in reasons.lower()
    ):
        return "release_or_provenance"
    if "pages: write" in scopes or "id-token: write" in scopes:
        return "deployment_or_oidc"
    if "security-events: write" in scopes:
        return "security_upload"
    if "contents: write" in scopes:
        return "repository_mutation"
    if {"issues: write", "pull-requests: write"} & scopes:
        return "pr_issue_interaction"
    return "other_write_scope"


def _permission_review_summary(
    permission_review_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}

    for entry in permission_review_matrix:
        kind = _permission_review_kind(entry)
        group = groups.setdefault(
            kind,
            {
                "kind": kind,
                "workflow_count": 0,
                "workflows": [],
                "granted_write_scopes": [],
                "requires_human_review": True,
                "safe_to_patch": False,
            },
        )
        group["workflow_count"] += 1
        group["workflows"].append(
            entry.get("path") or entry.get("workflow_path") or entry.get("file")
        )
        group["granted_write_scopes"] = sorted(
            set(group["granted_write_scopes"]) | set(entry.get("granted_write_scopes", []))
        )

    grouped = sorted(
        groups.values(),
        key=lambda item: (-int(item["workflow_count"]), str(item["kind"])),
    )

    return {
        "status": "human_review_required",
        "permission_review_count": len(permission_review_matrix),
        "group_count": len(grouped),
        "groups": grouped,
        "automatic_permission_reduction_allowed": False,
        "safe_to_patch": False,
        "review_first": True,
        "next_allowed_action": "collect_human_review_evidence",
        "blocked_actions": [
            "automatic_permission_reduction",
            "broad_workflow_permission_sweep",
            "security_alert_dismissal",
            "merge_authorization",
        ],
    }


def _permission_review_matrix(
    *,
    repo_root: Path,
    workflows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries = [
        _permission_review_entry(repo_root, workflow)
        for workflow in workflows
        if "permissions_least_privilege" in workflow.get("findings", [])
    ]
    return sorted(entries, key=lambda item: str(item["path"]))


def _permission_review_packet_strings(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return []


def _permission_review_evidence_packet(
    permission_review_matrix: list[dict[str, Any]],
    permission_review_summary: dict[str, Any],
) -> dict[str, Any]:
    required_evidence = [
        "workflow intent",
        "current granted write scopes",
        "inferred permission reasons from the report",
        "smallest reviewed permission-only change",
        "exact proof command",
        "reviewer decision",
    ]
    blocked_actions = [
        "automatic_permission_reduction",
        "broad_workflow_permission_sweep",
    ]

    review_tasks: list[dict[str, Any]] = []
    for entry in permission_review_matrix:
        workflow_path = str(
            entry.get("path") or entry.get("workflow_path") or entry.get("workflow") or "unknown"
        )
        granted_scopes = _permission_review_packet_strings(entry.get("granted_write_scopes"))
        inferred_reasons = _permission_review_packet_strings(
            entry.get("inferred_permission_reasons")
        )

        review_tasks.append(
            {
                "workflow": workflow_path,
                "permission_group": _permission_review_kind(entry),
                "granted_write_scopes": granted_scopes,
                "inferred_permission_reasons": inferred_reasons,
                "required_evidence": required_evidence,
                "reviewer_decision_required": True,
                "requires_human_review": True,
                "safe_to_patch": False,
                "recommended_change_type": "workflow_permission_review_evidence",
            }
        )

    status = "human_review_required" if review_tasks else "not_required"
    return {
        "schema_version": WORKFLOW_PERMISSION_REVIEW_EVIDENCE_SCHEMA_VERSION,
        "status": status,
        "permission_review_count": len(review_tasks),
        "automatic_permission_reduction_allowed": False,
        "review_first": True,
        "safe_to_patch": False,
        "next_allowed_action": "collect_human_review_evidence" if review_tasks else "none",
        "blocked_actions": blocked_actions if review_tasks else [],
        "required_human_evidence": required_evidence if review_tasks else [],
        "groups": permission_review_summary.get("groups", []),
        "review_tasks": review_tasks,
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
    permission_review_matrix = _permission_review_matrix(
        repo_root=root,
        workflows=workflows,
    )
    permission_review_summary = _permission_review_summary(permission_review_matrix)
    permission_review_evidence_packet = _permission_review_evidence_packet(
        permission_review_matrix,
        permission_review_summary,
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
        "permission_review_playbook": "docs/ci/workflow-permission-review-playbook.md",
        "permission_review_next_actions": [
            "Use the workflow permission review playbook before any permission reduction.",
            "Keep permission changes human-reviewed and one narrow workflow slice at a time.",
            "Do not patch permissions automatically when safe_to_patch is false.",
        ],
        "permission_review_matrix": permission_review_matrix,
        "permission_review_count": len(permission_review_matrix),
        "permission_review_summary": permission_review_summary,
        "permission_review_evidence_packet": permission_review_evidence_packet,
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

    lines.extend(["", "## Permission review summary", ""])
    permission_summary = payload.get("permission_review_summary", {})
    if isinstance(permission_summary, dict) and permission_summary:
        lines.append(f"- status: `{permission_summary.get('status', 'unknown')}`")
        lines.append(
            "- automatic_permission_reduction_allowed: "
            f"{str(bool(permission_summary.get('automatic_permission_reduction_allowed', False))).lower()}"
        )
        lines.append(
            f"- next_allowed_action: `{permission_summary.get('next_allowed_action', 'human_review')}`"
        )
        groups = permission_summary.get("groups", [])
        if isinstance(groups, list) and groups:
            lines.append("- groups:")
            for group in groups:
                lines.append(
                    f"  - `{group.get('kind')}`: {group.get('workflow_count', 0)} workflows"
                )

    packet = payload.get("permission_review_evidence_packet", {})
    if isinstance(packet, dict) and packet:
        lines.extend(["", "## Permission review evidence packet", ""])
        lines.append(f"- schema_version: `{packet.get('schema_version', 'unknown')}`")
        lines.append(f"- status: `{packet.get('status', 'unknown')}`")
        lines.append(
            "- automatic_permission_reduction_allowed: "
            f"{str(bool(packet.get('automatic_permission_reduction_allowed', False))).lower()}"
        )
        lines.append(f"- next_allowed_action: `{packet.get('next_allowed_action', 'none')}`")
        lines.append("- review_first: true")
        lines.append("- safe_to_patch: false")

        required = packet.get("required_human_evidence", [])
        if isinstance(required, list) and required:
            lines.extend(["", "### Required human evidence", ""])
            for item in required:
                lines.append(f"- `{item}`")

        blocked = packet.get("blocked_actions", [])
        if isinstance(blocked, list) and blocked:
            lines.extend(["", "### Blocked actions", ""])
            for item in blocked:
                lines.append(f"- `{item}`")

        review_tasks = packet.get("review_tasks", [])
        if isinstance(review_tasks, list) and review_tasks:
            lines.extend(["", "### Permission review tasks", ""])
            for task in review_tasks:
                if not isinstance(task, dict):
                    continue
                lines.append(f"#### {task.get('workflow', 'unknown')}")
                lines.append(f"- permission_group: `{task.get('permission_group', 'unknown')}`")
                lines.append("- reviewer_decision_required: true")
                lines.append("- requires_human_review: true")
                lines.append("- safe_to_patch: false")
                scopes = task.get("granted_write_scopes", [])
                if isinstance(scopes, list) and scopes:
                    lines.append("- granted_write_scopes:")
                    for scope in scopes:
                        lines.append(f"  - `{scope}`")
                reasons = task.get("inferred_permission_reasons", [])
                if isinstance(reasons, list) and reasons:
                    lines.append("- inferred_permission_reasons:")
                    for reason in reasons:
                        lines.append(f"  - {reason}")

    lines.extend(["", "## Permission review playbook", ""])
    playbook = payload.get("permission_review_playbook")
    if playbook:
        lines.append(f"- playbook: `{playbook}`")
    next_actions = payload.get("permission_review_next_actions", [])
    if next_actions:
        lines.append("- next_actions:")
        for action in next_actions:
            lines.append(f"  - {action}")
    lines.extend(["", "## Permission review matrix", ""])
    permission_review = payload.get("permission_review_matrix")
    if isinstance(permission_review, list) and permission_review:
        for entry in permission_review:
            if not isinstance(entry, dict):
                continue
            lines.append(f"### {entry.get('path', 'unknown')}")
            lines.append("")
            lines.append(
                f"- granted_write_scope_count: {entry.get('granted_write_scope_count', 0)}"
            )
            lines.append("- requires_human_review: true")
            lines.append("- safe_to_patch: false")
            scopes = entry.get("granted_write_scopes")
            if isinstance(scopes, list) and scopes:
                lines.append("- granted_write_scopes:")
                for scope in scopes:
                    lines.append(f"  - `{scope}`")
            reasons = entry.get("inferred_permission_reasons")
            if isinstance(reasons, list) and reasons:
                lines.append("- inferred_permission_reasons:")
                for reason in reasons:
                    lines.append(f"  - {reason}")
            lines.append("")
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
