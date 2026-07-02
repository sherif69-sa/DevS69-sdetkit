from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "sdetkit.workflow_governance.issue_policy.v1"


def build_policy_and_markdown(data: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(data, dict):
        data = {}

    summary_raw = data.get("summary")
    findings_raw = data.get("findings")
    finding_count_raw = data.get("finding_count")

    evidence_available = isinstance(summary_raw, dict) and isinstance(findings_raw, list)
    finding_count_valid = isinstance(finding_count_raw, int) and finding_count_raw >= 0
    findings = findings_raw if isinstance(findings_raw, list) else []
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    finding_count = finding_count_raw if finding_count_valid else 0
    finding_count_matches = finding_count_valid and finding_count == len(findings)

    actionable_reasons: list[str] = []
    if not evidence_available:
        actionable_reasons.append("workflow governance audit evidence unavailable or malformed")
    if not finding_count_valid:
        actionable_reasons.append("workflow governance finding count unavailable or malformed")
    elif not finding_count_matches:
        actionable_reasons.append("workflow governance finding count does not match evidence")
    if finding_count > 0:
        actionable_reasons.append(f"workflow governance findings: {finding_count}")

    actionable = bool(actionable_reasons)
    policy = {
        "schema_version": SCHEMA,
        "actionable": actionable,
        "workflow_finding_count": finding_count,
        "actionable_finding_count": len(actionable_reasons),
        "actionable_reasons": actionable_reasons,
        "evidence_available": evidence_available,
        "finding_count_valid": finding_count_valid,
        "finding_count_matches": finding_count_matches,
        "issue_policy": "rolling_tracker_when_actionable",
        "zero_finding_issue_creation": False,
    }

    missing_permissions = summary.get("missing_permissions")
    unpinned_uses = summary.get("unpinned_uses")
    missing_dispatch = summary.get("missing_dispatch")
    pr_target = summary.get("pr_target")

    lines = [
        "# Workflow governance audit",
        "",
        "This report keeps GitHub Actions permissions, pinning, and recovery posture reviewable.",
        "",
        "## Snapshot",
        f"- Workflows scanned: **{summary.get('workflow_count', 0)}**",
        f"- Findings: **{finding_count}**",
        f"- Audit evidence available: **{evidence_available}**",
        "",
        "## Missing top-level permissions",
    ]
    lines.extend(
        [f"- ⚠️ {name}" for name in missing_permissions]
        if isinstance(missing_permissions, list) and missing_permissions
        else ["- None"]
    )
    lines.extend(["", "## Unpinned reusable actions"])
    lines.extend(
        [
            f"- ⚠️ {item.get('workflow', 'unknown')} → "
            f"`{item.get('target', 'unknown')}`"
            for item in unpinned_uses
        ]
        if isinstance(unpinned_uses, list) and unpinned_uses
        else ["- None"]
    )
    lines.extend(["", "## Scheduled workflows missing manual recovery"])
    lines.extend(
        [f"- ⚠️ {name}" for name in missing_dispatch]
        if isinstance(missing_dispatch, list) and missing_dispatch
        else ["- None"]
    )
    lines.extend(["", "## pull_request_target usage"])
    lines.extend(
        [f"- ⚠️ {name}" for name in pr_target]
        if isinstance(pr_target, list) and pr_target
        else ["- None"]
    )

    if actionable:
        lines.extend(
            [
                "",
                "## Required follow-up",
                *[f"- {reason}" for reason in actionable_reasons],
                "",
                "A single rolling tracker is created or refreshed for these findings.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Result",
                "- Healthy workflow-governance evidence is retained as workflow artifacts.",
                "- No issue is created when the audit reports zero actionable findings.",
            ]
        )

    lines.extend(
        [
            "",
            "## Suggested follow-up",
            "- Add least-privilege top-level permissions where missing.",
            "- Pin reusable actions to full SHAs for deterministic supply-chain posture.",
            "- Ensure scheduled workflows can be re-run manually with `workflow_dispatch`.",
            "",
            "## Artifacts",
            "- `build/workflow-governance-audit.json`",
            "- `build/workflow-governance-policy.json`",
        ]
    )
    return policy, "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--policy-json", type=Path, required=True)
    parser.add_argument("--report-markdown", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    data = json.loads(args.audit_json.read_text(encoding="utf-8"))
    policy, markdown = build_policy_and_markdown(data)
    args.policy_json.write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.report_markdown.write_text(markdown, encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"actionable={'true' if policy['actionable'] else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
