from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final, TypedDict

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


def _architecture_layers(selected: list[Kit]) -> list[dict[str, object]]:
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


def _operating_model(selected: list[Kit], goal: str | None) -> list[dict[str, object]]:
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


def _upgrade_backlog(selected: list[Kit], goal: str | None) -> list[dict[str, object]]:
    goal_terms = _goal_tokens(goal)
    backlog: list[dict[str, object]] = []

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


def _doctor_lane(goal: str | None, repo_signals: dict[str, bool]) -> dict[str, object]:
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


def _quality_gate_lane(goal: str | None, repo_signals: dict[str, bool]) -> dict[str, object]:
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


def _integration_lane(goal: str | None, repo_signals: dict[str, bool]) -> dict[str, object]:
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


def _agentos_lane(goal: str | None, repo_signals: dict[str, bool]) -> dict[str, object]:
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


def _alignment_score(repo_signals: dict[str, bool]) -> dict[str, object]:
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


def _operating_sequence(
    doctor_lane: dict[str, object],
    quality_lane: dict[str, object],
    integration_lane: dict[str, object],
    agentos_lane: dict[str, object],
) -> list[dict[str, object]]:
    quality_commands = quality_lane.get("commands", [])
    integration_commands = integration_lane.get("commands", [])
    agent_commands = agentos_lane.get("commands", [])
    return [
        {
            "stage": "doctor-first",
            "summary": "Start with readiness, dependency drift, and repo-health diagnostics.",
            "commands": [doctor_lane["command"]],
        },
        {
            "stage": "quality-gate",
            "summary": "Use the deterministic merge bar and premium lane as the execution guardrail.",
            "commands": [str(item) for item in quality_commands],
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
    doctor_lane: dict[str, object],
    quality_lane: dict[str, object],
    integration_lane: dict[str, object],
) -> dict[str, object]:
    quality_commands = [str(item) for item in quality_lane.get("commands", [])]
    integration_commands = [str(item) for item in integration_lane.get("commands", [])]
    promotion_blockers = [
        "doctor must run before premium gate",
        "quality gate should inherit doctor upgrade-readiness findings",
    ]
    if integration_commands:
        promotion_blockers.append("topology checks must stay in the same review loop as premium gate")
    return {
        "entrypoint": doctor_lane["command"],
        "promotion_commands": quality_commands,
        "integration_commands": integration_commands,
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
    alignment_score = _alignment_score(repo_signals)
    operating_sequence = _operating_sequence(
        doctor_lane, quality_lane, integration_lane, agentos_lane
    )
    doctor_quality_contract = _doctor_quality_contract(
        doctor_lane, quality_lane, integration_lane
    )
    search_queries = _search_queries(goal)
    next_boosts = [
        {
            "id": "doctor-quality-sync",
            "title": "Align doctor with the quality gate",
            "summary": "Run doctor first, then quality.sh ci, so follow-up fixes land before premium-gate orchestration.",
            "commands": [doctor_lane["command"], *(quality_lane["commands"][:1])],
        },
        {
            "id": "umbrella-control-plane",
            "title": "Promote AgentOS as the umbrella review loop",
            "summary": "Capture blueprint, history, and dashboard outputs as the operating layer above the kits.",
            "commands": agentos_lane["commands"][:3],
        },
        {
            "id": "integration-proof",
            "title": "Keep topology proof in the release lane",
            "summary": "Make topology-check part of premium validation so umbrella architecture changes stay contract-safe.",
            "commands": integration_lane["commands"][:2],
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
            "primary_command": quality_lane["commands"][0] if quality_lane["commands"] else "",
        },
        {
            "domain": "premium-gate",
            "status": "ready" if repo_signals["premium_gate"] else "gap",
            "primary_command": (
                quality_lane["commands"][1]
                if len(quality_lane["commands"]) > 1
                else quality_lane["commands"][0]
                if quality_lane["commands"]
                else ""
            ),
        },
        {
            "domain": "integration-topology",
            "status": "ready" if repo_signals["topology_profile"] else "gap",
            "primary_command": (
                integration_lane["commands"][-1] if integration_lane["commands"] else ""
            ),
        },
        {
            "domain": "agentos",
            "status": "ready" if repo_signals["agent_templates"] else "partial",
            "primary_command": agentos_lane["commands"][0],
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
        "alignment_score": alignment_score,
        "alignment_matrix": alignment_matrix,
        "doctor_quality_contract": doctor_quality_contract,
        "operating_sequence": operating_sequence,
        "search_queries": search_queries,
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
    matches: list[dict[str, object]] = []
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
        ranked = search_payload(goal, limit=max(limit, 1) + len(resolved)).get("matches", [])
        for item in ranked:
            kit_payload = item.get("kit")
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


def _print_kit_detail(kit: dict[str, object]) -> None:
    print(f"{kit['id']} [{kit['stability']}]")
    print(f"route: sdetkit {kit['slug']} ...")
    print(f"summary: {kit['summary']}")
    print("capabilities:")
    for item in kit["capabilities"]:
        print(f"  - {item}")
    print("typical inputs:")
    for item in kit["typical_inputs"]:
        print(f"  - {item}")
    print("key artifacts:")
    for item in kit["key_artifacts"]:
        print(f"  - {item}")
    print("hero commands:")
    for cmd in kit["hero_commands"]:
        print(f"  - {cmd}")
    print("learning path:")
    for cmd in kit["learning_path"]:
        print(f"  - {cmd}")
    print("agent workflows:")
    for cmd in kit["agent_workflows"]:
        print(f"  - {cmd}")
    print("composes with:")
    for item in kit["composes_with"]:
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
        payload = {"schema_version": SCHEMA_VERSION, "kit": _kit_overview(kit)}
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
            return 0
        _print_kit_detail(payload["kit"])
        return 0

    if ns.action == "search":
        query = str(ns.query or ns.target or "").strip()
        if not query:
            sys.stderr.write("kits error: expected <query> for `sdetkit kits search <query>`\n")
            return 2
        payload = search_payload(query, limit=ns.limit)
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
            return 0
        print(f"Kit search results for: {query}")
        if not payload["matches"]:
            print("- no matches")
            return 0
        for item in payload["matches"]:
            kit = item["kit"]
            print(f"- {kit['id']} score={item['score']}")
            print(f"  matched: {', '.join(item['matched_terms']) or 'none'}")
            print(f"  summary: {kit['summary']}")
            print(f"  start with: {item['recommended_start']}")
            print(f"  agent workflow: {kit['agent_workflows'][0]}")
        return 0

    if ns.action == "blueprint":
        goal = str(ns.goal or ns.target or "").strip() or None
        payload = blueprint_payload(
            goal=goal,
            selected_kits=[str(item) for item in ns.selected_kits],
            limit=ns.limit,
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
            return 0
        print("Umbrella architecture blueprint")
        if goal:
            print(f"goal: {goal}")
        print("selected kits:")
        for kit in payload["selected_kits"]:
            print(f"- {kit['id']} ({kit['slug']})")
            print(f"  summary: {kit['summary']}")
            print(f"  compose with: {', '.join(kit['composes_with'])}")
            print(f"  start with: {kit['learning_path'][0]}")
        print("control plane:")
        print(f"- {payload['control_plane']['name']}: {payload['control_plane']['summary']}")
        for command in payload["control_plane"]["commands"]:
            print(f"  - {command}")
        print("phases:")
        for phase in payload["phases"]:
            print(f"- {phase['phase']}: {phase['summary']}")
        print("architecture layers:")
        for layer in payload["architecture_layers"]:
            print(f"- {layer['name']}: {layer['summary']}")
        print("operating model:")
        for lane in payload["operating_model"]:
            print(f"- {lane['cadence']}: {lane['focus']}")
        print("upgrade backlog:")
        for item in payload["upgrade_backlog"]:
            print(f"- {item['title']}: {item['summary']}")
        return 0

    if ns.action == "optimize":
        goal = str(ns.goal or ns.target or "").strip() or None
        payload = optimize_payload(
            root=Path(str(ns.repo_root)).resolve(),
            goal=goal,
            selected_kits=[str(item) for item in ns.selected_kits],
            limit=ns.limit,
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
            return 0
        print("Umbrella optimization plan")
        if goal:
            print(f"goal: {goal}")
        print(
            "alignment score: "
            f"{payload['alignment_score']['score']}% ({payload['alignment_score']['status']})"
        )
        print("alignment matrix:")
        for item in payload["alignment_matrix"]:
            print(f"- {item['domain']}: {item['status']}")
            if item["primary_command"]:
                print(f"  command: {item['primary_command']}")
        print("doctor/quality contract:")
        print(f"- entrypoint: {payload['doctor_quality_contract']['entrypoint']}")
        for command in payload["doctor_quality_contract"]["promotion_commands"]:
            print(f"  - promote with: {command}")
        print("doctor lane:")
        print(f"- {payload['doctor_lane']['command']}")
        print(f"  why: {payload['doctor_lane']['why']}")
        print("quality gate lane:")
        for command in payload["quality_gate_lane"]["commands"]:
            print(f"- {command}")
        print("integration lane:")
        for command in payload["integration_lane"]["commands"]:
            print(f"- {command}")
        print("agentos lane:")
        for command in payload["agentos_lane"]["commands"]:
            print(f"- {command}")
        print("operating sequence:")
        for item in payload["operating_sequence"]:
            print(f"- {item['stage']}: {item['summary']}")
        print("search queries:")
        for item in payload["search_queries"]:
            print(f"- {item['topic']}: {item['query']}")
        print("performance boosters:")
        for item in payload["performance_boosters"]:
            print(f"- {item['title']}: {item['detail']}")
        print("next boosts:")
        for item in payload["next_boosts"]:
            print(f"- {item['title']}: {item['summary']}")
        return 0

    if ns.target:
        sys.stderr.write("kits error: unexpected <target> for list action\n")
        return 2

    payload = list_payload()
    if ns.format == "json":
        sys.stdout.write(canonical_json_dumps(payload))
        return 0

    print("SDETKit umbrella kits")
    for kit in payload["kits"]:
        print(f"- {kit['id']} [{kit['stability']}]")
        print(f"  {kit['summary']}")
        print(f"  capabilities: {', '.join(kit['capabilities'])}")
        print(f"  start with: {kit['learning_path'][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
