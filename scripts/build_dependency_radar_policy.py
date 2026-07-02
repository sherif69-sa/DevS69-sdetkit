from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "sdetkit.dependency_radar.issue_policy.v1"


def _relativize_repo_paths(text: str, repo_root: Path) -> str:
    if not text:
        return text
    root = str(repo_root)
    normalized = text.replace(f"{root}/", "")
    return normalized.replace(root, ".")


def build_policy_and_markdown(
    data: Any,
    *,
    runtime_fast_follow: str,
    repo_root: Path,
) -> tuple[dict[str, Any], str]:
    if not isinstance(data, dict):
        data = {}
    packages_raw = data.get("packages")
    summary_raw = data.get("summary")
    evidence_available = isinstance(packages_raw, list) and isinstance(summary_raw, dict)
    packages = packages_raw[:5] if isinstance(packages_raw, list) else []
    route_map = packages_raw[:3] if isinstance(packages_raw, list) else []
    summary = summary_raw if isinstance(summary_raw, dict) else {}
    actionable_value = summary.get("actionable_packages")
    actionable_count_valid = isinstance(actionable_value, int) and actionable_value >= 0
    actionable_count = actionable_value if actionable_count_valid else 0

    actionable_reasons: list[str] = []
    if not evidence_available:
        actionable_reasons.append("dependency audit evidence unavailable or malformed")
    if not actionable_count_valid:
        actionable_reasons.append("actionable package count unavailable or malformed")
    if actionable_count > 0:
        actionable_reasons.append(f"actionable dependency packages: {actionable_count}")
    actionable = bool(actionable_reasons)

    policy = {
        "schema_version": SCHEMA,
        "actionable": actionable,
        "actionable_package_count": actionable_count,
        "actionable_finding_count": len(actionable_reasons),
        "actionable_reasons": actionable_reasons,
        "evidence_available": evidence_available,
        "actionable_count_valid": actionable_count_valid,
        "issue_policy": "rolling_tracker_when_actionable",
        "zero_finding_issue_creation": False,
    }

    audited = summary.get("packages_audited", len(packages_raw or []))
    lines = [
        "# Dependency radar",
        "",
        f"- Packages audited: **{audited}**",
        f"- Actionable packages: **{actionable_count}**",
        f"- Highest observed risk score: **{summary.get('max_risk_score', 0)}**",
        f"- Audit evidence available: **{evidence_available}**",
        "",
        "## Priority packages",
    ]
    if packages:
        for package in packages:
            lines.append(
                f"- **{package['name']}** · impact `{package.get('impact_area', 'unknown')}` "
                f"· usage `{package.get('repo_usage_tier', 'unknown')}` "
                f"· next `{package.get('manifest_action', 'watch')}`"
            )
    else:
        lines.append("- No packages returned by the audit for this scope.")

    lines.extend(["", "## Validation route map"])
    if route_map:
        for package in route_map:
            commands = package.get("validation_commands") or ["n/a"]
            backups = ", ".join(commands[:2]) or "n/a"
            lines.append(
                f"- **{package['name']}** → primary `{commands[0]}`; backups `{backups}`"
            )
    else:
        lines.append("- No validation routes were emitted for this run.")

    lines.extend(
        [
            "",
            "## Runtime fast-follow watchlist",
            _relativize_repo_paths(runtime_fast_follow.strip(), repo_root),
        ]
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
                "- Healthy dependency evidence is retained as workflow artifacts.",
                "- No issue is created when the audit reports zero actionable packages.",
            ]
        )
    lines.extend(
        [
            "",
            "## Recommended follow-up",
            "- Validate the hottest package lane before merging broad dependency refreshes.",
            "- Turn recurring runtime-core drift into a scoped enhancement or maintenance PR.",
            "",
            "## Artifacts",
            "- `build/dependency-radar.json`",
            "- `build/dependency-radar-policy.json`",
            "- `build/runtime-fast-follow.md`",
        ]
    )
    return policy, "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radar-json", type=Path, required=True)
    parser.add_argument("--runtime-markdown", type=Path, required=True)
    parser.add_argument("--policy-json", type=Path, required=True)
    parser.add_argument("--report-markdown", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    data = json.loads(args.radar_json.read_text(encoding="utf-8"))
    runtime_text = args.runtime_markdown.read_text(encoding="utf-8")
    policy, markdown = build_policy_and_markdown(
        data,
        runtime_fast_follow=runtime_text,
        repo_root=Path.cwd(),
    )
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
