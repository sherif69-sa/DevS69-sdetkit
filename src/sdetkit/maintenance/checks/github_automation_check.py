from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import CheckAction, CheckResult, MaintenanceContext

CHECK_NAME = "github_automation_check"
CHECK_MODES = {"quick", "full"}

_WORKFLOW_GROUPS: dict[str, dict[str, tuple[str, bool]]] = {
    "ghas_core": {
        "security.yml": ("CodeQL security scanning", True),
        "osv-scanner.yml": ("OSV SARIF ingestion", True),
        "dependency-audit.yml": ("pip-audit dependency scanning", True),
        "sbom.yml": ("SBOM export", True),
        "dependency-review.yml": ("PR dependency review gate", True),
    },
    "ghas_bots": {
        "ghas-review-bot.yml": ("Weekly GHAS digest bot", True),
        "ghas-campaign-bot.yml": ("GHAS campaign planner bot", True),
        "ghas-alert-sla-bot.yml": ("GHAS alert SLA tracker bot", True),
        "ghas-metrics-export-bot.yml": ("GHAS metrics export bot", True),
        "ghas-codeql-hotspots-bot.yml": ("GHAS CodeQL hotspots bot", True),
        "security-configuration-audit-bot.yml": (
            "GHAS security-configuration audit bot",
            True,
        ),
        "secret-protection-review-bot.yml": ("Secret protection review bot", True),
        "security-maintenance-bot.yml": ("Weekly security maintenance bot", True),
    },
    "upgrade_bots": {
        "dependency-radar-bot.yml": ("Dependency radar bot", True),
        "repo-optimization-bot.yml": ("Repo optimization control-loop bot", True),
        "workflow-governance-bot.yml": ("Workflow governance bot", True),
        "dependency-auto-merge.yml": ("Dependabot auto-merge bot", False),
        "pre-commit-autoupdate.yml": ("Pre-commit auto-update bot", False),
    },
    "expansion_bots": {
        "docs-experience-bot.yml": ("Docs experience radar bot", True),
        "release-readiness-radar-bot.yml": ("Release readiness radar bot", True),
        "worker-alignment-bot.yml": ("Worker alignment bot", True),
    },
    "collaboration_bots": {
        "pr-helper-bot.yml": ("PR helper bot", False),
        "pr-quality-comment.yml": ("PR quality comment bot", False),
        "contributor-onboarding-bot.yml": ("Contributor onboarding bot", False),
    },
}

_RECOMMENDED_CONFIGS: dict[str, str] = {
    ".github/dependabot.yml": "Dependabot update policy",
    ".github/codeql-config.yml": "CodeQL custom configuration",
    ".github/pip-audit-baseline.json": "pip-audit baseline",
}

_GHAS_UPDATE_TRACKS: list[dict[str, str]] = [
    {
        "id": "copilot_autofix",
        "title": "Copilot Autofix coverage",
        "description": (
            "Track GHAS remediation through CodeQL with Copilot Autofix-aware review loops "
            "and validate fixes in CI before merge."
        ),
        "workflow": "ghas-campaign-bot.yml",
    },
    {
        "id": "security_campaigns",
        "title": "Security campaign planning",
        "description": (
            "Use weekly issue-driven campaign planning so older code and secret alerts are "
            "grouped into targeted burn-down efforts."
        ),
        "workflow": "ghas-campaign-bot.yml",
    },
    {
        "id": "alert_sla_tracking",
        "title": "Alert SLA tracking",
        "description": (
            "Track age-based SLA breaches across code scanning, Dependabot, and secret "
            "scanning so older backlog slices are forced into an execution lane."
        ),
        "workflow": "ghas-alert-sla-bot.yml",
    },
    {
        "id": "metrics_exports",
        "title": "GHAS metrics export",
        "description": (
            "Export recurring GHAS metrics artifacts with severity, age-bucket, and "
            "workflow-freshness summaries so dashboards and audits have reusable evidence."
        ),
        "workflow": "ghas-metrics-export-bot.yml",
    },
    {
        "id": "codeql_hotspots",
        "title": "CodeQL hotspot batching",
        "description": (
            "Group open code-scanning alerts by rule and file so maintainers can batch-fix "
            "the hottest CodeQL hotspots instead of triaging alerts one-by-one."
        ),
        "workflow": "ghas-codeql-hotspots-bot.yml",
    },
    {
        "id": "security_configurations",
        "title": "Security configuration audits",
        "description": (
            "Audit repository-to-organization security configuration coverage and fall back "
            "gracefully when the repo is not org-managed."
        ),
        "workflow": "security-configuration-audit-bot.yml",
    },
    {
        "id": "secret_protection_controls",
        "title": "Secret protection control review",
        "description": (
            "Track push protection, delegated bypass, validity checks, and newer secret "
            "protection controls against the live secret-scanning backlog."
        ),
        "workflow": "secret-protection-review-bot.yml",
    },
    {
        "id": "dependency_review",
        "title": "Dependency review gate",
        "description": (
            "Fail pull requests when they introduce vulnerable dependencies or unacceptable "
            "license drift."
        ),
        "workflow": "dependency-review.yml",
    },
    {
        "id": "repo_optimization_loop",
        "title": "Repo optimization control loop",
        "description": (
            "Schedule optimize/expand intelligence so automation, feature, and search lanes "
            "keep producing actionable backlog slices."
        ),
        "workflow": "repo-optimization-bot.yml",
    },
    {
        "id": "workflow_governance",
        "title": "Workflow governance audit",
        "description": (
            "Audit workflow permissions, action pinning, and manual-recovery coverage so the "
            "automation surface stays deterministic and least-privilege."
        ),
        "workflow": "workflow-governance-bot.yml",
    },
]

_EXPANSION_UPDATE_TRACKS: list[dict[str, str]] = [
    {
        "id": "docs_experience_radar",
        "title": "Docs experience radar",
        "description": (
            "Review the docs surface as a product lane by tracking nav coverage, orphaned pages, "
            "flagship docs presence, and search-friendly entrypoints."
        ),
        "workflow": "docs-experience-bot.yml",
    },
    {
        "id": "release_readiness_radar",
        "title": "Release readiness radar",
        "description": (
            "Track the repo's release posture with doctor output, release workflow coverage, and "
            "freshness checks for roadmap, changelog, and release playbook assets."
        ),
        "workflow": "release-readiness-radar-bot.yml",
    },
    {
        "id": "worker_alignment",
        "title": "Worker alignment radar",
        "description": (
            "Run the aligned worker templates together so expansion guidance, dependency review, "
            "docs posture, and release readiness stay synchronized with the repo's base code."
        ),
        "workflow": "worker-alignment-bot.yml",
    },
]


def _workflow_presence(repo_root: Path) -> dict[str, dict[str, Any]]:
    workflow_dir = repo_root / ".github" / "workflows"
    present_files = (
        {path.name for path in workflow_dir.iterdir() if path.is_file()}
        if workflow_dir.exists()
        else set()
    )

    result: dict[str, dict[str, Any]] = {}
    for group_name, files in _WORKFLOW_GROUPS.items():
        entries: list[dict[str, Any]] = []
        missing_required = 0
        for filename, (summary, required) in files.items():
            present = filename in present_files
            if required and not present:
                missing_required += 1
            entries.append(
                {
                    "file": filename,
                    "summary": summary,
                    "required": required,
                    "present": present,
                }
            )
        result[group_name] = {
            "items": entries,
            "present": sum(1 for item in entries if item["present"]),
            "total": len(entries),
            "missing_required": missing_required,
        }
    return result


def _config_presence(repo_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for rel_path, summary in sorted(_RECOMMENDED_CONFIGS.items()):
        items.append(
            {
                "path": rel_path,
                "summary": summary,
                "present": (repo_root / rel_path).exists(),
            }
        )
    return items


def run(ctx: MaintenanceContext) -> CheckResult:
    workflow_groups = _workflow_presence(ctx.repo_root)
    config_items = _config_presence(ctx.repo_root)

    all_items = [
        item
        for group in workflow_groups.values()
        for item in group["items"]
        if isinstance(item, dict)
    ]
    missing_required = [
        item["file"] for item in all_items if item["required"] and not item["present"]
    ]
    missing_configs = [item["path"] for item in config_items if not item["present"]]

    tracked_updates: list[dict[str, Any]] = []
    for update in _GHAS_UPDATE_TRACKS:
        workflow = update["workflow"]
        tracked_updates.append(
            {
                **update,
                "present": workflow not in missing_required
                and (ctx.repo_root / ".github" / "workflows" / workflow).exists(),
            }
        )
    expansion_tracks: list[dict[str, Any]] = []
    for update in _EXPANSION_UPDATE_TRACKS:
        workflow = update["workflow"]
        expansion_tracks.append(
            {
                **update,
                "present": workflow not in missing_required
                and (ctx.repo_root / ".github" / "workflows" / workflow).exists(),
            }
        )

    ok = not missing_required and not missing_configs
    summary = "GitHub automation coverage is complete across GHAS, dependency review, and maintenance bots"
    if not ok:
        summary = (
            f"GitHub automation is missing {len(missing_required)} required workflow(s) "
            f"and {len(missing_configs)} supporting config file(s)"
        )

    actions: list[CheckAction] = []
    for filename in missing_required[:6]:
        actions.append(
            CheckAction(
                id=f"add-{filename.replace('.', '-').replace('_', '-')}",
                title=f"Add `{filename}` to close GitHub automation coverage gaps",
                applied=False,
                notes="Review docs/automation-bots.md for the recommended operating loop.",
            )
        )
    for rel_path in missing_configs[:3]:
        actions.append(
            CheckAction(
                id=f"restore-{rel_path.replace('/', '-').replace('.', '-')}",
                title=f"Restore `{rel_path}` so automation has its expected policy/config input",
                applied=False,
                notes="These files are part of the repo's expected GHAS and dependency hygiene baseline.",
            )
        )
    actions.append(
        CheckAction(
            id="review-automation-bots-docs",
            title="Review `docs/automation-bots.md` and align workflow inventory with the repo's active bot surface",
            applied=False,
            notes="Use `python -m sdetkit maintenance --include-check github_automation_check --format md` for a compact status report.",
        )
    )

    return CheckResult(
        ok=ok,
        summary=summary,
        details={
            "workflow_groups": workflow_groups,
            "config_items": config_items,
            "missing_required_workflows": missing_required,
            "missing_configs": missing_configs,
            "ghas_update_tracks": tracked_updates,
            "expansion_update_tracks": expansion_tracks,
        },
        actions=actions,
    )
