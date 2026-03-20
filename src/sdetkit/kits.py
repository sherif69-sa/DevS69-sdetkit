from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Final, TypedDict

from . import upgrade_audit
from .atomicio import canonical_json_dumps

SCHEMA_VERSION: Final[str] = "sdetkit.kits.catalog.v1"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Kit(TypedDict):
    id: str
    slug: str
    stability: str
    summary: str
    hero_commands: list[str]
    capabilities: list[str]
    typical_inputs: list[str]
    key_artifacts: list[str]
    learning_path: list[str]
    search_terms: list[str]
    agent_workflows: list[str]
    composes_with: list[str]


Payload = dict[str, Any]


_KITS: Final[list[Kit]] = [
    {
        "id": "release-confidence",
        "slug": "release",
        "stability": "stable",
        "summary": "Gate, doctor, repo audit, security, evidence, and release readiness.",
        "hero_commands": [
            "sdetkit release gate fast",
            "sdetkit release gate release",
            "sdetkit release doctor",
            "sdetkit release evidence",
        ],
        "capabilities": [
            "Pre-merge quality gates",
            "Release preflight diagnostics",
            "Policy and security enforcement",
            "Evidence packaging for approvals",
        ],
        "typical_inputs": [
            "Repository working tree",
            "CI configuration",
            "Quality and policy baselines",
        ],
        "key_artifacts": [
            "Gate JSON summaries",
            "Doctor readiness reports",
            "Release evidence bundles",
        ],
        "learning_path": [
            "sdetkit release gate fast",
            "sdetkit release doctor",
            "sdetkit release gate release",
        ],
        "search_terms": [
            "release",
            "gate",
            "doctor",
            "repo",
            "evidence",
            "security",
            "readiness",
            "approval",
            "compliance",
            "quality",
            "umbrella",
        ],
        "agent_workflows": [
            "sdetkit agent init",
            "sdetkit agent run 'template:repo-health-audit' --approve",
            "sdetkit agent dashboard build --format html",
        ],
        "composes_with": ["test-intelligence", "failure-forensics"],
    },
    {
        "id": "test-intelligence",
        "slug": "intelligence",
        "stability": "stable",
        "summary": "Flake classification, deterministic env capture, impact summaries, and governance hooks.",
        "hero_commands": [
            "sdetkit intelligence flake classify --history history.json",
            "sdetkit intelligence impact summarize --changed changed.txt --map testmap.json",
            "sdetkit intelligence capture-env",
            "sdetkit intelligence upgrade-audit --format json --top 5",
        ],
        "capabilities": [
            "Flake and failure classification",
            "Change impact summaries",
            "Environment capture for reproducibility",
            "Signal shaping for quality governance",
            "Dependency upgrade prioritization",
        ],
        "typical_inputs": [
            "Failure history JSON",
            "Changed file lists",
            "Test ownership or mapping data",
        ],
        "key_artifacts": [
            "Flake classification reports",
            "Impact summaries",
            "Captured environment snapshots",
            "Upgrade-risk and maintenance-lane reports",
        ],
        "learning_path": [
            "sdetkit intelligence capture-env",
            "sdetkit intelligence flake classify --history history.json",
            "sdetkit intelligence impact summarize --changed changed.txt --map testmap.json",
            "sdetkit intelligence upgrade-audit --format json --top 5",
        ],
        "search_terms": [
            "flakes",
            "failure",
            "triage",
            "impact",
            "upgrade",
            "dependency",
            "search",
            "classification",
            "risk",
            "agentos",
            "optimization",
        ],
        "agent_workflows": [
            "sdetkit agent run 'template:report-dashboard' --approve",
            'sdetkit agent run \'action repo.audit {"profile":"default"}\' --approve',
            "sdetkit agent dashboard build --format md",
        ],
        "composes_with": ["release-confidence", "integration-assurance"],
    },
    {
        "id": "integration-assurance",
        "slug": "integration",
        "stability": "stable",
        "summary": "Offline-first service profile and environment readiness contracts.",
        "hero_commands": [
            "sdetkit integration check --profile integration-profile.json",
            "sdetkit integration matrix --profile integration-profile.json",
            "sdetkit integration topology-check --profile heterogeneous-topology.json",
        ],
        "capabilities": [
            "Service profile validation",
            "Environment readiness checks",
            "Dependency topology validation",
            "Cross-system contract coverage",
        ],
        "typical_inputs": [
            "Integration profile JSON",
            "Topology maps",
            "Environment dependency metadata",
        ],
        "key_artifacts": [
            "Integration readiness reports",
            "Matrix coverage outputs",
            "Topology contract artifacts",
        ],
        "learning_path": [
            "sdetkit integration check --profile integration-profile.json",
            "sdetkit integration matrix --profile integration-profile.json",
            "sdetkit integration topology-check --profile heterogeneous-topology.json",
        ],
        "search_terms": [
            "integration",
            "topology",
            "service",
            "environment",
            "contract",
            "readiness",
            "matrix",
            "profile",
            "umbrella",
            "architecture",
        ],
        "agent_workflows": [
            "sdetkit agent init",
            "sdetkit agent run 'template:security-governance-summary' --approve",
            "sdetkit agent dashboard build --format json",
        ],
        "composes_with": ["release-confidence", "failure-forensics"],
    },
    {
        "id": "failure-forensics",
        "slug": "forensics",
        "stability": "stable",
        "summary": "Run-to-run regression intelligence, evidence diffing, and deterministic repro bundle generation.",
        "hero_commands": [
            "sdetkit forensics compare --from old.json --to new.json",
            "sdetkit forensics bundle --run run.json --output bundle.zip",
            "sdetkit forensics bundle-diff --from-bundle old.zip --to-bundle new.zip",
        ],
        "capabilities": [
            "Run-to-run diff analysis",
            "Deterministic repro bundle generation",
            "Evidence comparisons across failures",
            "Escalation-ready debugging packs",
        ],
        "typical_inputs": [
            "Structured run result JSON",
            "Historical evidence bundles",
            "Build or test failure metadata",
        ],
        "key_artifacts": [
            "Forensics diff summaries",
            "Repro ZIP bundles",
            "Bundle-to-bundle comparison outputs",
        ],
        "learning_path": [
            "sdetkit forensics compare --from old.json --to new.json",
            "sdetkit forensics bundle --run run.json --output bundle.zip",
            "sdetkit forensics bundle-diff --from-bundle old.zip --to-bundle new.zip",
        ],
        "search_terms": [
            "forensics",
            "repro",
            "bundle",
            "regression",
            "diff",
            "incident",
            "debugging",
            "evidence",
            "quality",
        ],
        "agent_workflows": [
            "sdetkit agent run 'template:report-dashboard' --approve",
            "sdetkit agent history export --format csv --output .sdetkit/agent/workdir/history-summary.csv",
            "sdetkit agent dashboard build --format html",
        ],
        "composes_with": ["release-confidence", "test-intelligence"],
    },
]


def _resolve_kit(name: str) -> Kit | None:
    needle = name.strip().lower()
    for item in _KITS:
        kit_id = str(item.get("id", "")).lower()
        slug = str(item.get("slug", "")).lower()
        if needle in {kit_id, slug}:
            return item
    return None


def _tokenize(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.lower())


def _kit_search_blob(kit: Kit) -> dict[str, set[str]]:
    return {
        "exact": set(_tokenize(f"{kit['id']} {kit['slug']}")) | {kit["id"], kit["slug"]},
        "keywords": set(_tokenize(" ".join(kit["search_terms"]))),
        "summary": set(_tokenize(kit["summary"])),
        "capabilities": set(_tokenize(" ".join(kit["capabilities"]))),
        "artifacts": set(_tokenize(" ".join(kit["key_artifacts"]))),
        "commands": set(_tokenize(" ".join(kit["hero_commands"] + kit["learning_path"]))),
        "agent": set(_tokenize(" ".join(kit["agent_workflows"]))),
        "compose": set(_tokenize(" ".join(kit["composes_with"]))),
    }


def _score_kit(kit: Kit, query: str) -> tuple[int, list[str]]:
    terms = _tokenize(query)
    if not terms:
        return 0, []
    blob = _kit_search_blob(kit)
    matched: list[str] = []
    score = 0
    for term in terms:
        if term in blob["exact"]:
            score += 10
        elif term in blob["keywords"]:
            score += 7
        elif term in blob["summary"] or term in blob["capabilities"]:
            score += 5
        elif term in blob["artifacts"] or term in blob["commands"]:
            score += 3
        elif term in blob["agent"] or term in blob["compose"]:
            score += 2
        else:
            continue
        matched.append(term)
    return score, sorted(set(matched))


def _kit_overview(kit: Kit) -> dict[str, object]:
    return {
        "id": kit["id"],
        "slug": kit["slug"],
        "stability": kit["stability"],
        "summary": kit["summary"],
        "capabilities": kit["capabilities"],
        "typical_inputs": kit["typical_inputs"],
        "key_artifacts": kit["key_artifacts"],
        "hero_commands": kit["hero_commands"],
        "learning_path": kit["learning_path"],
        "agent_workflows": kit["agent_workflows"],
        "composes_with": kit["composes_with"],
    }


def _goal_tokens(goal: str | None) -> set[str]:
    if goal is None:
        return set()
    return set(_tokenize(goal))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _payload_list(value: object) -> list[Payload]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _payload_dict(value: object) -> Payload:
    return value if isinstance(value, dict) else {}


def _architecture_layers(selected: list[Kit]) -> list[Payload]:
    return [
        {
            "name": "experience-surface",
            "summary": "Umbrella kits stay the product entrypoint so teams discover the right lane quickly.",
            "components": [f"sdetkit {kit['slug']} ..." for kit in selected],
        },
        {
            "name": "control-plane",
            "summary": (
                "AgentOS coordinates recurring runs, review loops, history capture, and artifact "
                "exports above the kit surfaces."
            ),
            "components": [
                "sdetkit agent init",
                "sdetkit agent run '<goal>' --approve",
                "sdetkit agent dashboard build --format html",
            ],
        },
        {
            "name": "artifact-plane",
            "summary": "Every lane emits deterministic artifacts that can be wired into CI, reviews, and evidence packs.",
            "components": sorted(
                {artifact for kit in selected for artifact in kit["key_artifacts"]}
            ),
        },
    ]


def _operating_model(selected: list[Kit], goal: str | None) -> list[Payload]:
    goal_text = goal or "umbrella upgrade"
    return [
        {
            "cadence": "continuous",
            "focus": "Discovery and routing",
            "commands": [
                "sdetkit kits search topology",
                f'sdetkit kits blueprint --goal "{goal_text}"',
            ],
        },
        {
            "cadence": "per-change",
            "focus": "Execution and deterministic artifact generation",
            "commands": [kit["learning_path"][0] for kit in selected],
        },
        {
            "cadence": "daily-or-release",
            "focus": "AgentOS control-plane review",
            "commands": [
                f'sdetkit agent run "{goal_text}" --approve',
                "sdetkit agent history list --limit 10",
                "sdetkit agent dashboard build --format html",
            ],
        },
    ]


def _upgrade_backlog(selected: list[Kit], goal: str | None) -> list[Payload]:
    goal_terms = _goal_tokens(goal)
    backlog: list[Payload] = []

    def add_upgrade(
        upgrade_id: str,
        title: str,
        summary: str,
        commands: list[str],
        triggers: set[str],
    ) -> None:
        if triggers and goal_terms and goal_terms.isdisjoint(triggers):
            return
        backlog.append(
            {
                "id": upgrade_id,
                "title": title,
                "summary": summary,
                "commands": commands,
            }
        )

    add_upgrade(
        "umbrella-routing",
        "Tighten umbrella routing",
        "Use kit search and kit composition to route incoming work to the smallest reliable lane.",
        [
            "sdetkit kits list",
            "sdetkit kits search upgrade risk",
            "sdetkit kits blueprint --goal 'umbrella routing hardening'",
        ],
        {"umbrella", "architecture", "search", "upgrade"},
    )
    add_upgrade(
        "agent-control-plane",
        "Promote AgentOS to the recurring control plane",
        "Run repeatable orchestration, history export, and dashboard builds as the management layer over kits.",
        [
            "sdetkit agent init",
            "sdetkit agent run 'template:repo-health-audit' --approve",
            "sdetkit agent dashboard build --format html",
        ],
        {"agent", "agentos", "automation", "control", "orchestration", "upgrade"},
    )
    add_upgrade(
        "integration-topology",
        "Expand topology-aware integration assurance",
        "Treat heterogeneous dependency maps and environment contracts as first-class release inputs.",
        [
            "sdetkit integration check --profile examples/kits/integration/profile.json",
            "sdetkit integration topology-check --profile examples/kits/integration/heterogeneous-topology.json",
        ],
        {"integration", "topology", "umbrella", "architecture"},
    )
    add_upgrade(
        "release-upgrade-audit",
        "Fold dependency maintenance into release readiness",
        "Prioritize upgrade work using the intelligence lane so release decisions carry freshness and validation guidance.",
        [
            "sdetkit intelligence upgrade-audit --format json --top 5",
            "sdetkit release doctor",
        ],
        {"upgrade", "dependency", "release", "optimization"},
    )
    add_upgrade(
        "forensics-feedback-loop",
        "Feed forensics back into the umbrella",
        "Close the loop by comparing run deltas and using evidence bundles to improve the release and integration lanes.",
        [
            "sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json",
            "sdetkit forensics bundle --run examples/kits/forensics/run-b.json --output build/repro.zip",
        ],
        {"forensics", "failure", "incident", "optimization"},
    )

    if not backlog:
        for upgrade in (
            {
                "id": "umbrella-routing",
                "title": "Tighten umbrella routing",
                "summary": "Use kit search and blueprinting to keep the public surface crisp as capabilities grow.",
                "commands": ["sdetkit kits search release evidence"],
            },
            {
                "id": "agent-control-plane",
                "title": "Promote AgentOS to the recurring control plane",
                "summary": "Capture deterministic history and dashboards above the execution kits.",
                "commands": ["sdetkit agent dashboard build --format html"],
            },
        ):
            backlog.append(upgrade)
    return backlog


def _repo_signal(root: Path, relpath: str) -> bool:
    return (root / relpath).exists()


def _doctor_lane(goal: str | None, repo_signals: dict[str, bool]) -> Payload:
    goal_terms = _goal_tokens(goal)
    flags = ["--dev", "--ci", "--repo"]
    focus = ["developer-experience", "repo-health"]
    if repo_signals.get("pyproject"):
        flags.append("--deps")
        focus.append("dependency-policy")
    if "upgrade" in goal_terms or "optimization" in goal_terms or "quality" in goal_terms:
        flags.append("--upgrade-audit")
        focus.append("upgrade-readiness")
    if repo_signals.get("topology_profile") and (
        {"umbrella", "architecture", "integration", "topology"} & goal_terms
    ):
        focus.append("topology-follow-through")
    command = "sdetkit doctor " + " ".join(flags) + " --format json"
    return {
        "focus_areas": focus,
        "command": command,
        "why": (
            "Start with a single doctor run that aligns repo health, CI posture, dependency drift, "
            "and upgrade-readiness hints before deeper gate work."
        ),
    }


def _quality_gate_lane(goal: str | None, repo_signals: dict[str, bool]) -> Payload:
    goal_terms = _goal_tokens(goal)
    commands: list[str] = []
    if repo_signals.get("quality_script"):
        commands.append("bash quality.sh ci")
    if repo_signals.get("premium_gate"):
        premium_mode = "full" if {"architecture", "umbrella", "doctor"} & goal_terms else "fast"
        commands.append(f"bash premium-gate.sh --mode {premium_mode}")
    if repo_signals.get("ci_script"):
        commands.append("bash ci.sh")
    return {
        "commands": commands,
        "policy": (
            "Use quality.sh as the fast deterministic merge bar, then premium gate as the umbrella "
            "orchestration proof that doctor, topology, security, and evidence stay aligned."
        ),
    }


def _integration_lane(goal: str | None, repo_signals: dict[str, bool]) -> Payload:
    commands: list[str] = []
    if repo_signals.get("integration_profile"):
        commands.append(
            "sdetkit integration check --profile examples/kits/integration/profile.json"
        )
    if repo_signals.get("topology_profile"):
        commands.append(
            "sdetkit integration topology-check --profile "
            "examples/kits/integration/heterogeneous-topology.json"
        )
    coverage = (
        "topology-aware"
        if repo_signals.get("topology_profile")
        else "profile-only"
        if repo_signals.get("integration_profile")
        else "missing"
    )
    return {
        "coverage": coverage,
        "commands": commands,
        "why": (
            "Treat integration contracts as a release input so umbrella routing, premium gate, "
            "and AgentOS all evaluate the same topology truth."
        ),
    }


def _agentos_lane(goal: str | None, repo_signals: dict[str, bool]) -> Payload:
    goal_text = goal or "umbrella optimization"
    commands = [
        "sdetkit agent init",
        f'sdetkit agent run "{goal_text}" --approve',
        "sdetkit agent dashboard build --format html",
    ]
    if repo_signals.get("agent_templates"):
        commands.insert(1, "sdetkit agent run 'template:repo-health-audit' --approve")
    return {
        "commands": commands,
        "why": (
            "AgentOS becomes the recurring control plane that captures execution history and "
            "exports a stable dashboard for the umbrella architecture."
        ),
    }


def _performance_boosters(repo_signals: dict[str, bool]) -> list[dict[str, str]]:
    boosters: list[dict[str, str]] = []
    if repo_signals.get("constraints"):
        boosters.append(
            {
                "id": "ci-constraints",
                "title": "Pinned CI toolchain",
                "detail": "Keep constraints-ci.txt as the reproducible install baseline for fast, low-drift CI bootstrap.",
            }
        )
    if repo_signals.get("gate_snapshot"):
        boosters.append(
            {
                "id": "fast-gate-snapshot",
                "title": "Fast gate baseline",
                "detail": "Reuse the checked-in fast gate snapshot to preserve deterministic quick feedback loops.",
            }
        )
    if repo_signals.get("premium_gate") and repo_signals.get("topology_profile"):
        boosters.append(
            {
                "id": "topology-premium-loop",
                "title": "Topology-backed premium scoring",
                "detail": "Feed topology artifacts into premium gate so umbrella upgrades fail on contract drift instead of late manual review.",
            }
        )
    if repo_signals.get("agent_templates"):
        boosters.append(
            {
                "id": "agent-templates",
                "title": "Agent template reuse",
                "detail": "Lean on repo automation templates so recurring audits and dashboards stay standardized instead of bespoke.",
            }
        )
    return boosters


def _alignment_status(ready: int, total: int) -> str:
    if total <= 0:
        return "unknown"
    ratio = ready / total
    if ratio >= 0.9:
        return "maximized"
    if ratio >= 0.7:
        return "strong"
    if ratio >= 0.4:
        return "partial"
    return "needs-work"


def _alignment_score(repo_signals: dict[str, bool]) -> Payload:
    weighted_signals = [
        ("quality_script", 2),
        ("premium_gate", 2),
        ("ci_script", 1),
        ("constraints", 1),
        ("gate_snapshot", 1),
        ("integration_profile", 1),
        ("topology_profile", 2),
        ("agent_templates", 2),
        ("pyproject", 1),
    ]
    total = sum(weight for _signal, weight in weighted_signals)
    earned = sum(weight for signal, weight in weighted_signals if repo_signals.get(signal))
    score = int(round((earned / total) * 100)) if total else 0
    ready = sum(1 for signal, _weight in weighted_signals if repo_signals.get(signal))
    return {
        "score": score,
        "ready_signals": ready,
        "total_signals": len(weighted_signals),
        "status": _alignment_status(ready, len(weighted_signals)),
    }


def _search_queries(goal: str | None) -> list[dict[str, str]]:
    goal_text = goal or "umbrella optimization"
    return [
        {
            "topic": "doctor-upgrade-lane",
            "query": f"{goal_text} doctor upgrade audit quality gate",
        },
        {
            "topic": "agentos-control-plane",
            "query": f"{goal_text} agentos control plane dashboard history",
        },
        {
            "topic": "integration-topology",
            "query": f"{goal_text} integration topology premium gate",
        },
    ]


def _upgrade_inventory(root: Path) -> Payload:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return {
            "status": "missing",
            "summary": "No pyproject.toml was found, so upgrade inventory could not be derived.",
            "packages_audited": 0,
            "priority_packages": [],
            "impact_summary": [],
            "validation_summary": [],
            "group_summary": [],
            "source_summary": [],
            "recommended_commands": [],
        }

    requirement_paths = upgrade_audit._discover_requirement_files(root, include_lockfiles=False)
    dependencies = upgrade_audit._load_dependencies(pyproject_path, requirement_paths)
    if not dependencies:
        return {
            "status": "empty",
            "summary": "No dependency manifests were discovered for upgrade inventory planning.",
            "packages_audited": 0,
            "priority_packages": [],
            "impact_summary": [],
            "validation_summary": [],
            "group_summary": [],
            "source_summary": [],
            "recommended_commands": [],
        }

    by_package: dict[str, list[upgrade_audit.Dependency]] = {}
    for dep in dependencies:
        by_package.setdefault(dep.name, []).append(dep)

    package_names = sorted(by_package)
    project_python_requires = upgrade_audit._load_project_python_requires(pyproject_path)
    repo_usage = upgrade_audit._collect_repo_usage(root, package_names)
    reports: list[upgrade_audit.PackageReport] = []
    for package in package_names:
        deps = by_package[package]
        baseline_version = upgrade_audit._pick_current_version(deps)
        reports.append(
            upgrade_audit._build_package_report(
                package,
                deps,
                latest_version=baseline_version,
                release_date=None,
                project_python_requires=project_python_requires,
                compatible_version=baseline_version,
                compatible_release_date=None,
                compatibility_status="manifest-baseline",
                metadata_source="manifest",
                repo_usage_files=repo_usage.get(package, []),
            )
        )

    reports = upgrade_audit._sort_reports(reports)
    priority_packages = sorted(
        reports,
        key=lambda report: (
            -report.repo_usage_count,
            report.impact_area != "runtime-core",
            report.name,
        ),
    )[:5]
    hot_path_present = any(report.repo_usage_tier == "hot-path" for report in reports)
    runtime_core_present = any(report.impact_area == "runtime-core" for report in reports)
    top_validation = upgrade_audit._validation_summary(reports)
    recommended_commands = [
        "python -m sdetkit intelligence upgrade-audit --format json --top 5",
    ]
    if hot_path_present:
        recommended_commands.append(
            "python -m sdetkit intelligence upgrade-audit --used-in-repo-only "
            "--repo-usage-tier hot-path --top 5 --format md"
        )
    if runtime_core_present:
        recommended_commands.append(
            "python -m sdetkit intelligence upgrade-audit --impact-area runtime-core "
            "--repo-usage-tier hot-path --top 3 --format json"
        )
    if top_validation:
        recommended_commands.append(
            "python -m sdetkit intelligence upgrade-audit --validation-command "
            f"\"{top_validation[0]['command']}\" --format md"
        )

    return {
        "status": "ready",
        "summary": (
            "Manifest-aware upgrade inventory built from declared dependencies, observed repo usage, "
            "impact areas, and validation lanes."
        ),
        "packages_audited": len(reports),
        "priority_packages": [
            {
                "name": report.name,
                "impact_area": report.impact_area,
                "repo_usage_tier": report.repo_usage_tier,
                "repo_usage_count": report.repo_usage_count,
                "groups": report.groups,
                "validation_commands": report.validation_commands,
            }
            for report in priority_packages
        ],
        "impact_summary": upgrade_audit._impact_summary(reports)[:4],
        "validation_summary": top_validation[:4],
        "group_summary": upgrade_audit._group_summary(reports)[:4],
        "source_summary": upgrade_audit._source_summary(reports)[:4],
        "release_freshness_summary": upgrade_audit._release_freshness_summary(reports)[:4],
        "recommended_commands": recommended_commands,
    }


def _upgrade_execution_lane(upgrade_inventory: Payload) -> Payload:
    recommended_commands = [str(item) for item in _string_list(upgrade_inventory.get("recommended_commands"))]
    priority_packages = _payload_list(upgrade_inventory.get("priority_packages"))
    focus = []
    if priority_packages:
        top = priority_packages[0]
        focus.append(
            f"Start with {top['name']} because it is {top['repo_usage_tier']} in the repo "
            f"and lands in the {top['impact_area']} impact area."
        )
    if any(item.get("impact_area") == "quality-tooling" for item in priority_packages):
        focus.append("Keep quality-tooling upgrades coupled to the same validation lane as release confidence.")
    if any(item.get("impact_area") == "runtime-core" for item in priority_packages):
        focus.append("Treat runtime-core dependencies as first-class release inputs before broader maintenance batches.")
    return {
        "summary": (
            "Translate upgrade inventory into a narrow execution lane so dependency maintenance stays "
            "aligned with repo usage and validation coverage."
        ),
        "focus": focus,
        "commands": recommended_commands,
    }


def _innovation_opportunities(
    goal: str | None,
    repo_signals: dict[str, bool],
    upgrade_inventory: Payload,
) -> list[Payload]:
    goal_text = goal or "umbrella optimization"
    opportunities: list[Payload] = []
    validation_summary = _payload_list(upgrade_inventory.get("validation_summary"))
    impact_summary = _payload_list(upgrade_inventory.get("impact_summary"))
    source_summary = _payload_list(upgrade_inventory.get("source_summary"))
    fresh_release_present = any(
        item.get("release_freshness") == "fresh-release"
        for item in _payload_list(upgrade_inventory.get("release_freshness_summary"))
    )

    if upgrade_inventory.get("status") == "ready":
        commands = [
            "python -m sdetkit intelligence upgrade-audit --format json --top 10",
        ]
        if repo_signals.get("agent_templates"):
            commands.append(
                "sdetkit agent run 'template:dependency-outdated-report' --approve"
            )
        commands.append("sdetkit agent dashboard build --format html")
        opportunities.append(
            {
                "id": "dependency-radar",
                "title": "Create a recurring dependency radar",
                "summary": (
                    "Turn the manifest-aware upgrade inventory into a scheduled artifact so hot-path "
                    "packages, validation lanes, and maintenance drift stay visible between releases."
                ),
                "why_now": (
                    f"The repo already exposes upgrade-aware inventory for "
                    f"{upgrade_inventory.get('packages_audited', 0)} packages."
                ),
                "commands": commands,
            }
        )

    if validation_summary:
        top_validation = validation_summary[0]
        opportunities.append(
            {
                "id": "validation-command-index",
                "title": "Publish a package-to-validation command index",
                "summary": (
                    "Materialize the strongest validation lanes into a searchable map so dependency "
                    "changes and refactors always point to the smallest safe verification loop."
                ),
                "why_now": (
                    "The optimize inventory already knows which validation commands cover the hottest "
                    f"dependency sets, starting with `{top_validation.get('command', '')}`."
                ),
                "commands": [
                    "python -m sdetkit intelligence upgrade-audit --format md",
                    "python -m sdetkit doctor --upgrade-audit --format md",
                ],
            }
        )

    if any(item.get("impact_area") == "integration-adapters" for item in impact_summary):
        opportunities.append(
            {
                "id": "adapter-activation",
                "title": "Activate optional notification adapters with smoke coverage",
                "summary": (
                    "Convert declared integration-adapter dependencies into clearly documented and "
                    "lightly validated quickstarts so optional channels feel productized, not latent."
                ),
                "why_now": (
                    "The upgrade inventory shows optional adapter surface area that can become a more "
                    "discoverable feature set for contributors and operators."
                ),
                "commands": [
                    "python -m pytest -q tests/test_notify_plugins.py",
                    "python -m sdetkit kits describe integration",
                ],
            }
        )

    if any(item.get("impact_area") == "runtime-core" for item in impact_summary):
        opportunities.append(
            {
                "id": "runtime-core-fast-follow",
                "title": "Add a runtime-core fast-follow watchlist",
                "summary": (
                    "Keep the repo's hottest runtime dependencies on a tighter review cadence so "
                    "transport, API, and security surfaces do not age silently."
                ),
                "why_now": (
                    "The optimize inventory identifies runtime-core packages as first-class upgrade "
                    "inputs, which makes them good candidates for a separate watchlist artifact."
                ),
                "commands": [
                    "python -m sdetkit intelligence upgrade-audit --impact-area runtime-core --format md",
                    "bash quality.sh cov",
                ],
            }
        )

    if repo_signals.get("constraints") and source_summary:
        opportunities.append(
            {
                "id": "manifest-drift-scorecard",
                "title": "Add a manifest drift scorecard",
                "summary": (
                    "Summarize which manifests dominate the maintenance surface so lockfiles, test "
                    "constraints, and package metadata evolve with less hidden drift."
                ),
                "why_now": (
                    "The repo already mixes pyproject and requirement manifests, making cross-source "
                    "visibility a useful maintenance feature."
                ),
                "commands": [
                    "python -m sdetkit intelligence upgrade-audit --format json",
                    f'sdetkit kits optimize --goal "{goal_text}" --format json',
                ],
            }
        )

    if fresh_release_present and repo_signals.get("quality_script"):
        opportunities.append(
            {
                "id": "fresh-release-fast-lane",
                "title": "Create a fresh-release fast lane",
                "summary": (
                    "Treat newly published upstream releases as a separate queue that reruns the "
                    "smallest quality bar before they age into larger maintenance batches."
                ),
                "why_now": (
                    "Fast-follow validation is cheaper when fresh releases are reviewed explicitly "
                    "instead of being mixed into a generic backlog."
                ),
                "commands": [
                    "python -m sdetkit intelligence upgrade-audit --max-release-age-days 14 --format md",
                    "bash quality.sh ci",
                ],
            }
        )

    return opportunities[:5]


def _auto_fix_lane(
    repo_signals: dict[str, bool], quality_lane: Payload, goal: str | None
) -> Payload:
    commands: list[str] = []
    if repo_signals.get("quality_script"):
        commands.append("bash quality.sh type")
    if repo_signals.get("premium_gate"):
        commands.append(
            "python -m sdetkit.premium_gate_engine --out-dir .sdetkit/out "
            "--double-check --auto-fix --auto-run-scripts --format markdown"
        )
    if repo_signals.get("quality_script"):
        commands.extend(_string_list(quality_lane.get("commands"))[:1])
    if goal and {"umbrella", "architecture", "agentos"} & _goal_tokens(goal):
        commands.append(
            'sdetkit agent run "upgrade umbrella architecture with agentos optimization" --approve'
        )
    return {
        "commands": commands,
        "policy": (
            "Use the premium gate engine as the intelligent remediation layer so typing, "
            "doctor follow-ups, and scripted repairs converge before the main merge bar reruns."
        ),
    }


def _quality_boost_lane(goal: str | None) -> Payload:
    goal_text = goal or "umbrella optimization"
    return {
        "command": "bash quality.sh boost",
        "goal": goal_text,
        "why": (
            "Use a single boost lane to align doctor, intelligent auto-fix, deterministic quality "
            "checks, topology proof, and umbrella optimization output."
        ),
        "phases": [
            "doctor-first",
            "intelligent-autofix",
            "quality-gate",
            "integration-proof",
            "umbrella-optimize",
        ],
    }


def _operating_sequence(
    doctor_lane: Payload,
    quality_lane: Payload,
    integration_lane: Payload,
    agentos_lane: Payload,
    auto_fix_lane: Payload,
) -> list[Payload]:
    quality_commands = _string_list(quality_lane.get("commands"))
    integration_commands = _string_list(integration_lane.get("commands"))
    agent_commands = _string_list(agentos_lane.get("commands"))
    return [
        {
            "stage": "doctor-first",
            "summary": "Start with readiness, dependency drift, and repo-health diagnostics.",
            "commands": [str(doctor_lane["command"])],
        },
        {
            "stage": "intelligent-autofix",
            "summary": "Promote premium auto-fix and scripted remediation before the full gate reruns.",
            "commands": _string_list(auto_fix_lane.get("commands")),
        },
        {
            "stage": "quality-gate",
            "summary": "Use the deterministic merge bar and premium lane as the execution guardrail.",
            "commands": quality_commands,
        },
        {
            "stage": "integration-proof",
            "summary": "Refresh topology-aware proof so architecture changes stay contract-safe.",
            "commands": [str(item) for item in integration_commands],
        },
        {
            "stage": "agentos-governance",
            "summary": "Capture the execution lane in AgentOS so history and dashboards stay in sync.",
            "commands": [str(item) for item in agent_commands],
        },
    ]


def _doctor_quality_contract(
    doctor_lane: Payload,
    quality_lane: Payload,
    integration_lane: Payload,
    auto_fix_lane: Payload,
) -> Payload:
    quality_commands = _string_list(quality_lane.get("commands"))
    integration_commands = _string_list(integration_lane.get("commands"))
    promotion_blockers = [
        "doctor must run before premium gate",
        "quality gate should inherit doctor upgrade-readiness findings",
        "auto-fix lane should repair obvious issues before the premium gate reruns",
    ]
    if integration_commands:
        promotion_blockers.append(
            "topology checks must stay in the same review loop as premium gate"
        )
    return {
        "entrypoint": doctor_lane["command"],
        "promotion_commands": quality_commands,
        "integration_commands": integration_commands,
        "auto_fix_commands": _string_list(auto_fix_lane.get("commands")),
        "promotion_blockers": promotion_blockers,
    }


def optimize_payload(
    *,
    root: Path,
    goal: str | None,
    selected_kits: list[str],
    limit: int = 3,
) -> dict[str, object]:
    blueprint = blueprint_payload(goal=goal, selected_kits=selected_kits, limit=limit)
    upgrade_inventory = _upgrade_inventory(root)
    repo_signals = {
        "pyproject": _repo_signal(root, "pyproject.toml"),
        "quality_script": _repo_signal(root, "quality.sh"),
        "premium_gate": _repo_signal(root, "premium-gate.sh"),
        "ci_script": _repo_signal(root, "ci.sh"),
        "constraints": _repo_signal(root, "constraints-ci.txt"),
        "gate_snapshot": _repo_signal(root, ".sdetkit/gate.fast.snapshot.json"),
        "integration_profile": _repo_signal(root, "examples/kits/integration/profile.json"),
        "topology_profile": _repo_signal(
            root, "examples/kits/integration/heterogeneous-topology.json"
        ),
        "agent_templates": _repo_signal(root, "templates/automations/repo-health-audit.yaml"),
    }
    doctor_lane = _doctor_lane(goal, repo_signals)
    quality_lane = _quality_gate_lane(goal, repo_signals)
    integration_lane = _integration_lane(goal, repo_signals)
    agentos_lane = _agentos_lane(goal, repo_signals)
    auto_fix_lane = _auto_fix_lane(repo_signals, quality_lane, goal)
    quality_boost_lane = _quality_boost_lane(goal)
    alignment_score = _alignment_score(repo_signals)
    operating_sequence = _operating_sequence(
        doctor_lane, quality_lane, integration_lane, agentos_lane, auto_fix_lane
    )
    doctor_quality_contract = _doctor_quality_contract(
        doctor_lane, quality_lane, integration_lane, auto_fix_lane
    )
    search_queries = _search_queries(goal)
    upgrade_execution_lane = _upgrade_execution_lane(upgrade_inventory)
    innovation_opportunities = _innovation_opportunities(goal, repo_signals, upgrade_inventory)
    next_boosts = [
        {
            "id": "quality-boost",
            "title": "Collapse the umbrella flow into a single boost command",
            "summary": "Run doctor, auto-fix, premium validation, topology proof, and optimization reporting in one lane.",
            "commands": [str(quality_boost_lane["command"])],
        },
        {
            "id": "doctor-quality-sync",
            "title": "Align doctor with the quality gate",
            "summary": "Run doctor first, then quality.sh ci, so follow-up fixes land before premium-gate orchestration.",
            "commands": [
                str(doctor_lane["command"]),
                *_string_list(quality_lane.get("commands"))[:1],
            ],
        },
        {
            "id": "intelligent-auto-fix",
            "title": "Auto-fix quality and premium-gate regressions intelligently",
            "summary": "Use the premium engine and targeted typing gates to repair issues before rerunning the umbrella flow.",
            "commands": _string_list(auto_fix_lane.get("commands"))[:3],
        },
        {
            "id": "umbrella-control-plane",
            "title": "Promote AgentOS as the umbrella review loop",
            "summary": "Capture blueprint, history, and dashboard outputs as the operating layer above the kits.",
            "commands": _string_list(agentos_lane.get("commands"))[:3],
        },
        {
            "id": "integration-proof",
            "title": "Keep topology proof in the release lane",
            "summary": "Make topology-check part of premium validation so umbrella architecture changes stay contract-safe.",
            "commands": _string_list(integration_lane.get("commands"))[:2],
        },
    ]
    alignment_matrix = [
        {
            "domain": "doctor",
            "status": "ready" if repo_signals["pyproject"] else "gap",
            "primary_command": doctor_lane["command"],
        },
        {
            "domain": "quality-gate",
            "status": "ready" if repo_signals["quality_script"] else "gap",
            "primary_command": _string_list(quality_lane.get("commands"))[0]
            if _string_list(quality_lane.get("commands"))
            else "",
        },
        {
            "domain": "premium-gate",
            "status": "ready" if repo_signals["premium_gate"] else "gap",
            "primary_command": (
                _string_list(quality_lane.get("commands"))[1]
                if len(_string_list(quality_lane.get("commands"))) > 1
                else _string_list(quality_lane.get("commands"))[0]
                if _string_list(quality_lane.get("commands"))
                else ""
            ),
        },
        {
            "domain": "integration-topology",
            "status": "ready" if repo_signals["topology_profile"] else "gap",
            "primary_command": (
                _string_list(integration_lane.get("commands"))[-1]
                if _string_list(integration_lane.get("commands"))
                else ""
            ),
        },
        {
            "domain": "agentos",
            "status": "ready" if repo_signals["agent_templates"] else "partial",
            "primary_command": _string_list(agentos_lane.get("commands"))[0],
        },
    ]
    missing_domains = [item["domain"] for item in alignment_matrix if item["status"] != "ready"]
    return {
        "schema_version": SCHEMA_VERSION,
        "goal": goal,
        "selected_kits": blueprint["selected_kits"],
        "blueprint": blueprint,
        "repo_signals": repo_signals,
        "doctor_lane": doctor_lane,
        "quality_gate_lane": quality_lane,
        "integration_lane": integration_lane,
        "agentos_lane": agentos_lane,
        "auto_fix_lane": auto_fix_lane,
        "quality_boost_lane": quality_boost_lane,
        "alignment_score": alignment_score,
        "alignment_matrix": alignment_matrix,
        "doctor_quality_contract": doctor_quality_contract,
        "operating_sequence": operating_sequence,
        "search_queries": search_queries,
        "upgrade_inventory": upgrade_inventory,
        "upgrade_execution_lane": upgrade_execution_lane,
        "innovation_opportunities": innovation_opportunities,
        "missing_domains": missing_domains,
        "performance_boosters": _performance_boosters(repo_signals),
        "next_boosts": next_boosts,
    }


def list_payload() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kits": sorted((_kit_overview(kit) for kit in _KITS), key=lambda item: str(item["id"])),
    }


def search_payload(query: str, *, limit: int = 4) -> dict[str, object]:
    matches: list[Payload] = []
    for kit in _KITS:
        score, matched_terms = _score_kit(kit, query)
        if score <= 0:
            continue
        matches.append(
            {
                "kit": _kit_overview(kit),
                "score": score,
                "matched_terms": matched_terms,
                "recommended_start": kit["learning_path"][0],
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["kit"]["id"])))
    return {
        "schema_version": SCHEMA_VERSION,
        "query": query,
        "matches": matches[: max(limit, 1)],
    }


def blueprint_payload(
    *, goal: str | None, selected_kits: list[str], limit: int = 3
) -> dict[str, object]:
    resolved: list[Kit] = []
    seen: set[str] = set()
    for item in selected_kits:
        kit = _resolve_kit(item)
        if kit is not None and kit["id"] not in seen:
            resolved.append(kit)
            seen.add(kit["id"])

    if goal:
        ranked = _payload_list(
            search_payload(goal, limit=max(limit, 1) + len(resolved)).get("matches", [])
        )
        for ranked_item in ranked:
            kit_payload = ranked_item.get("kit")
            if not isinstance(kit_payload, dict):
                continue
            kit_id = str(kit_payload.get("id", ""))
            kit = _resolve_kit(kit_id)
            if kit is not None and kit_id not in seen:
                resolved.append(kit)
                seen.add(kit_id)
            if len(resolved) >= max(limit, 1):
                break

    if not resolved:
        resolved = list(_KITS[: max(limit, 1)])

    phases = [
        {
            "phase": "discover",
            "summary": "Map the repo problem to the smallest useful umbrella surface.",
            "commands": [
                "sdetkit kits list",
                *(f"sdetkit kits describe {kit['slug']}" for kit in resolved),
            ],
        },
        {
            "phase": "execute",
            "summary": "Run the selected kits in a deliberate sequence that produces reusable artifacts.",
            "kit_sequence": [
                {
                    "id": kit["id"],
                    "summary": kit["summary"],
                    "commands": kit["learning_path"],
                    "agent_workflows": kit["agent_workflows"],
                }
                for kit in resolved
            ],
        },
        {
            "phase": "govern",
            "summary": "Use AgentOS as the control plane for recurring runs, history, and review-ready dashboards.",
            "commands": [
                "sdetkit agent init",
                "sdetkit agent history list --limit 10",
                "sdetkit agent dashboard build --format html",
            ],
        },
    ]

    control_plane = {
        "name": "agentos-control-plane",
        "summary": (
            "AgentOS sits above the umbrella kits as a deterministic control plane for repeatable "
            "automation, history, and dashboard exports."
        ),
        "commands": [
            "sdetkit agent init",
            "sdetkit agent run 'template:repo-health-audit' --approve",
            "sdetkit agent dashboard build --format html",
        ],
    }
    architecture_layers = _architecture_layers(resolved[: max(limit, 1)])
    operating_model = _operating_model(resolved[: max(limit, 1)], goal)
    upgrade_backlog = _upgrade_backlog(resolved[: max(limit, 1)], goal)
    metrics = [
        "kit routing accuracy",
        "artifact coverage per execution lane",
        "AgentOS run success rate",
        "time-to-evidence for release and incident review",
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "goal": goal,
        "selected_kits": [_kit_overview(kit) for kit in resolved[: max(limit, 1)]],
        "control_plane": control_plane,
        "phases": phases,
        "architecture_layers": architecture_layers,
        "operating_model": operating_model,
        "upgrade_backlog": upgrade_backlog,
        "metrics": metrics,
    }


def _print_kit_detail(kit: Payload) -> None:
    print(f"{kit['id']} [{kit['stability']}]")
    print(f"route: sdetkit {kit['slug']} ...")
    print(f"summary: {kit['summary']}")
    print("capabilities:")
    for item in _string_list(kit["capabilities"]):
        print(f"  - {item}")
    print("typical inputs:")
    for item in _string_list(kit["typical_inputs"]):
        print(f"  - {item}")
    print("key artifacts:")
    for item in _string_list(kit["key_artifacts"]):
        print(f"  - {item}")
    print("hero commands:")
    for cmd in _string_list(kit["hero_commands"]):
        print(f"  - {cmd}")
    print("learning path:")
    for cmd in _string_list(kit["learning_path"]):
        print(f"  - {cmd}")
    print("agent workflows:")
    for cmd in _string_list(kit["agent_workflows"]):
        print(f"  - {cmd}")
    print("composes with:")
    for item in _string_list(kit["composes_with"]):
        print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit kits",
        description="Discover umbrella kit surfaces, search them, and build cross-kit blueprints.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="list",
        choices=["list", "describe", "search", "blueprint", "optimize"],
    )
    parser.add_argument("target", nargs="?", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--query", default=None, help="Free-text search query for `search`.")
    parser.add_argument("--goal", default=None, help="Goal statement for `blueprint`.")
    parser.add_argument(
        "--kit",
        dest="selected_kits",
        action="append",
        default=[],
        help="Explicit kit to include in `blueprint` (repeatable).",
    )
    parser.add_argument("--limit", type=int, default=4, help="Maximum search or blueprint results.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to inspect for `optimize` alignment planning.",
    )
    ns = parser.parse_args(argv)

    if ns.action == "describe":
        if not ns.target:
            sys.stderr.write("kits error: expected <kit> for `sdetkit kits describe <kit>`\n")
            return 2
        kit = _resolve_kit(str(ns.target))
        if kit is None:
            sys.stderr.write(f"kits error: unknown kit '{ns.target}'\n")
            return 2
        detail_payload: Payload = {"schema_version": SCHEMA_VERSION, "kit": _kit_overview(kit)}
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(detail_payload))
            return 0
        _print_kit_detail(detail_payload["kit"])
        return 0

    if ns.action == "search":
        query = str(ns.query or ns.target or "").strip()
        if not query:
            sys.stderr.write("kits error: expected <query> for `sdetkit kits search <query>`\n")
            return 2
        search_result = search_payload(query, limit=ns.limit)
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(search_result))
            return 0
        matches = _payload_list(search_result.get("matches"))
        print(f"Kit search results for: {query}")
        if not matches:
            print("- no matches")
            return 0
        for item in matches:
            kit = item["kit"]
            print(f"- {kit['id']} score={item['score']}")
            print(f"  matched: {', '.join(item['matched_terms']) or 'none'}")
            print(f"  summary: {kit['summary']}")
            print(f"  start with: {item['recommended_start']}")
            print(f"  agent workflow: {kit['agent_workflows'][0]}")
        return 0

    if ns.action == "blueprint":
        goal = str(ns.goal or ns.target or "").strip() or None
        blueprint_result = blueprint_payload(
            goal=goal,
            selected_kits=[str(item) for item in ns.selected_kits],
            limit=ns.limit,
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(blueprint_result))
            return 0
        print("Umbrella architecture blueprint")
        if goal:
            print(f"goal: {goal}")
        print("selected kits:")
        for kit_item in _payload_list(blueprint_result.get("selected_kits")):
            print(f"- {kit_item['id']} ({kit_item['slug']})")
            print(f"  summary: {kit_item['summary']}")
            print(f"  compose with: {', '.join(_string_list(kit_item['composes_with']))}")
            print(f"  start with: {_string_list(kit_item['learning_path'])[0]}")
        print("control plane:")
        control_plane = _payload_dict(blueprint_result.get("control_plane"))
        print(f"- {control_plane['name']}: {control_plane['summary']}")
        for command in _string_list(control_plane["commands"]):
            print(f"  - {command}")
        print("phases:")
        for phase in _payload_list(blueprint_result.get("phases")):
            print(f"- {phase['phase']}: {phase['summary']}")
        print("architecture layers:")
        for layer in _payload_list(blueprint_result.get("architecture_layers")):
            print(f"- {layer['name']}: {layer['summary']}")
        print("operating model:")
        for lane in _payload_list(blueprint_result.get("operating_model")):
            print(f"- {lane['cadence']}: {lane['focus']}")
        print("upgrade backlog:")
        for item in _payload_list(blueprint_result.get("upgrade_backlog")):
            print(f"- {item['title']}: {item['summary']}")
        return 0

    if ns.action == "optimize":
        goal = str(ns.goal or ns.target or "").strip() or None
        optimize_result = optimize_payload(
            root=Path(str(ns.repo_root)).resolve(),
            goal=goal,
            selected_kits=[str(item) for item in ns.selected_kits],
            limit=ns.limit,
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(optimize_result))
            return 0
        print("Umbrella optimization plan")
        if goal:
            print(f"goal: {goal}")
        alignment_score = _payload_dict(optimize_result.get("alignment_score"))
        print(f"alignment score: {alignment_score['score']}% ({alignment_score['status']})")
        print("alignment matrix:")
        for item in _payload_list(optimize_result.get("alignment_matrix")):
            print(f"- {item['domain']}: {item['status']}")
            if item["primary_command"]:
                print(f"  command: {item['primary_command']}")
        print("doctor/quality contract:")
        contract = _payload_dict(optimize_result.get("doctor_quality_contract"))
        print(f"- entrypoint: {contract['entrypoint']}")
        for command in _string_list(contract["promotion_commands"]):
            print(f"  - promote with: {command}")
        for command in _string_list(contract.get("auto_fix_commands")):
            print(f"  - auto-fix with: {command}")
        print("doctor lane:")
        doctor_lane = _payload_dict(optimize_result.get("doctor_lane"))
        print(f"- {doctor_lane['command']}")
        print(f"  why: {doctor_lane['why']}")
        print("quality gate lane:")
        quality_gate_lane = _payload_dict(optimize_result.get("quality_gate_lane"))
        for command in _string_list(quality_gate_lane["commands"]):
            print(f"- {command}")
        print("auto-fix lane:")
        auto_fix_lane = _payload_dict(optimize_result.get("auto_fix_lane"))
        for command in _string_list(auto_fix_lane["commands"]):
            print(f"- {command}")
        print("quality boost lane:")
        quality_boost_lane = _payload_dict(optimize_result.get("quality_boost_lane"))
        print(f"- {quality_boost_lane['command']}")
        print(f"  why: {quality_boost_lane['why']}")
        print("integration lane:")
        integration_lane = _payload_dict(optimize_result.get("integration_lane"))
        for command in _string_list(integration_lane["commands"]):
            print(f"- {command}")
        print("agentos lane:")
        agentos_lane = _payload_dict(optimize_result.get("agentos_lane"))
        for command in _string_list(agentos_lane["commands"]):
            print(f"- {command}")
        print("operating sequence:")
        for item in _payload_list(optimize_result.get("operating_sequence")):
            print(f"- {item['stage']}: {item['summary']}")
        print("search queries:")
        for item in _payload_list(optimize_result.get("search_queries")):
            print(f"- {item['topic']}: {item['query']}")
        print("performance boosters:")
        for item in _payload_list(optimize_result.get("performance_boosters")):
            print(f"- {item['title']}: {item['detail']}")
        print("innovation opportunities:")
        for item in _payload_list(optimize_result.get("innovation_opportunities")):
            print(f"- {item['title']}: {item['summary']}")
            print(f"  why now: {item['why_now']}")
        print("next boosts:")
        for item in _payload_list(optimize_result.get("next_boosts")):
            print(f"- {item['title']}: {item['summary']}")
        return 0

    if ns.target:
        sys.stderr.write("kits error: unexpected <target> for list action\n")
        return 2

    list_result = list_payload()
    if ns.format == "json":
        sys.stdout.write(canonical_json_dumps(list_result))
        return 0

    print("SDETKit umbrella kits")
    for kit_item in _payload_list(list_result.get("kits")):
        print(f"- {kit_item['id']} [{kit_item['stability']}]")
        print(f"  {kit_item['summary']}")
        print(f"  capabilities: {', '.join(_string_list(kit_item['capabilities']))}")
        print(f"  start with: {_string_list(kit_item['learning_path'])[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
