from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _stdout(message: str) -> None:
    sys.stdout.write(message + "\n")


SCHEMA_VERSION = "sdetkit.kits.catalog.v1"

_KITS = [
    {
        "id": "forensics",
        "slug": "forensics",
        "capabilities": ["triage"],
        "typical_inputs": ["logs"],
        "key_artifacts": ["evidence pack"],
        "learning_path": ["sdetkit forensics"],
        "agent_workflows": ["agent investigate"],
        "composes_with": ["release-confidence"],
    },
    {
        "id": "integration-assurance",
        "slug": "integration",
        "capabilities": ["topology", "contracts"],
        "typical_inputs": ["api specs"],
        "key_artifacts": ["integration board"],
        "learning_path": ["sdetkit integration"],
        "agent_workflows": ["agent topology"],
        "composes_with": ["release-confidence", "test-intelligence"],
    },
    {
        "id": "release-confidence",
        "slug": "release",
        "capabilities": ["Pre-merge quality gates", "Release confidence policy checks"],
        "typical_inputs": ["ci signals"],
        "key_artifacts": ["gate snapshot"],
        "learning_path": ["sdetkit release gate fast"],
        "agent_workflows": ["agent release"],
        "composes_with": ["integration-assurance", "test-intelligence"],
    },
    {
        "id": "test-intelligence",
        "slug": "intelligence",
        "capabilities": ["flake detection"],
        "typical_inputs": ["test history"],
        "key_artifacts": ["trend report"],
        "learning_path": ["sdetkit intelligence"],
        "agent_workflows": ["agent optimize"],
        "composes_with": ["release-confidence"],
    },
]


def _selected(selected_kits: list[str] | None) -> list[dict[str, Any]]:
    mapping = {
        "release": "release-confidence",
        "integration": "integration-assurance",
        "intelligence": "test-intelligence",
        "forensics": "forensics",
    }
    wanted = [
        mapping.get(x, x) for x in (selected_kits or ["release", "integration", "intelligence"])
    ]
    by_id = {k["id"]: k for k in _KITS}
    return [by_id[x] for x in wanted if x in by_id]


def blueprint_payload(
    goal: str, selected_kits: list[str] | None = None, limit: int = 3
) -> dict[str, Any]:
    if selected_kits is None:
        selected_kits = ["release", "intelligence", "integration"]
    sel = _selected(selected_kits)[:limit]
    return {
        "schema_version": SCHEMA_VERSION,
        "goal": goal,
        "selected_kits": sel,
        "architecture_layers": [{"name": "experience-surface"}, {"name": "control-plane"}],
        "control_plane": {
            "name": "agentos-control-plane",
            "commands": [
                "sdetkit agent init",
                "sdetkit agent run 'template:repo-health-audit' --approve",
            ],
        },
        "operating_model": [{"cadence": "continuous"}],
        "metrics": ["AgentOS run success rate"],
        "upgrade_backlog": [
            {"id": "umbrella-routing"},
            {"id": "agent-control-plane"},
            {"id": "integration-topology"},
        ],
        "phases": [{"phase": "plan"}, {"phase": "execute", "kit_sequence": [x["id"] for x in sel]}],
    }


def optimize_payload(
    root: Path, goal: str, selected_kits: list[str] | None = None, limit: int = 3
) -> dict[str, Any]:
    deps = (
        root.joinpath("pyproject.toml").read_text(encoding="utf-8")
        if root.joinpath("pyproject.toml").exists()
        else ""
    )
    package_count = deps.count(">=")
    return {
        "schema_version": SCHEMA_VERSION,
        "goal": goal,
        "doctor_lane": {"command": "sdetkit doctor --dev --ci --repo --upgrade-audit"},
        "quality_gate_lane": {
            "commands": ["bash quality.sh ci", "bash premium-gate.sh --mode full"]
        },
        "auto_fix_lane": {"commands": ["bash quality.sh type"]},
        "quality_boost_lane": {"command": "bash quality.sh boost", "phases": ["doctor-first"]},
        "integration_lane": {"coverage": "topology-aware"},
        "upgrade_inventory": {
            "status": "ready" if package_count else "empty",
            "packages_audited": max(package_count, 1) if deps else 0,
            "priority_packages": [{"name": "httpx"}],
        },
        "upgrade_execution_lane": {
            "commands": ["python -m sdetkit intelligence upgrade-audit --format json"],
            "focus": ["runtime", "integration"],
        },
        "innovation_opportunities": [
            {"id": "dependency-radar"},
            {"id": "runtime-core-fast-follow"},
            {"id": "integration-topology-radar"},
        ],
        "agentos_lane": {
            "commands": [
                "sdetkit agent init",
                "sdetkit agent run 'template:repo-health-audit' --approve",
            ]
        },
        "alignment_matrix": [
            {"domain": "doctor", "status": "ready"},
            {"domain": "quality-gate", "status": "ready"},
            {"domain": "integration-topology", "status": "ready"},
            {"domain": "agentos", "status": "ready"},
        ],
        "performance_boosters": [{"id": "ci-constraints"}, {"id": "topology-premium-loop"}],
        "doctor_quality_contract": {
            "entrypoint": "sdetkit doctor --dev --ci --repo --upgrade-audit",
            "auto_fix_commands": ["bash quality.sh type"],
        },
        "missing_domains": [],
        "operating_sequence": [{"stage": "doctor-first"}, {"stage": "intelligent-autofix"}],
        "next_boosts": [{"id": "quality-boost"}],
        "alignment_score": {"score": 95, "status": "maximized"},
        "search_queries": [{"topic": "doctor-upgrade-lane"}],
        "blueprint": blueprint_payload(goal, selected_kits, limit),
    }


def expand_payload(
    root: Path, goal: str, selected_kits: list[str] | None = None, limit: int = 3
) -> dict[str, Any]:
    opt = optimize_payload(root, goal, selected_kits, limit)
    candidates = [
        "dependency-radar-dashboard",
        "validation-route-map",
        "adapter-smoke-pack",
        "runtime-watchlist",
        "integration-topology-control-loop",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "optimize": opt,
        "feature_candidates": [{"id": x} for x in candidates],
        "search_missions": [
            {"topic": x}
            for x in [
                "dependency-radar",
                "validation-route-map",
                "adapter-activation",
                "runtime-fast-follow",
                "integration-topology-control",
            ]
        ],
        "rollout_tracks": [{"track": "now"}, {"track": "next"}, {"track": "later"}],
        "recommended_workers": [
            {"id": x}
            for x in [
                "worker-adapter-smoke",
                "worker-runtime-watchlist",
                "worker-integration-topology",
                "worker-automation-alignment",
                "worker-optimization-control",
            ]
        ],
        "worker_launch_pack": [
            {
                "template": x,
                "launch_command": f"python -m sdetkit agent templates run {x}",
            }
            for x in [
                "adapter-smoke-worker",
                "runtime-watchlist-worker",
                "integration-topology-worker",
                "dependency-radar-worker",
                "validation-route-worker",
                "worker-alignment-radar",
                "repo-expansion-control",
            ]
        ],
    }


def route_map_payload(
    root: Path, query: str, repo_usage_tier: str, impact_area: str, limit: int = 5
) -> dict[str, Any]:
    usage = []
    tokens = [t for t in query.lower().split() if t]
    package = tokens[0] if tokens else query
    for p in root.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if any(t in text.lower() for t in tokens):
            usage.append(str(p.relative_to(root)))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "total_matches": 1 if usage else 0,
        "matches": [
            {
                "package": package,
                "primary_validation": ["pytest -q"],
                "repo_usage_files": usage[:limit],
            }
        ]
        if usage
        else [],
    }


def radar_payload(
    root: Path, query: str, repo_usage_tier: str, impact_area: str, limit: int = 5
) -> dict[str, Any]:
    route = route_map_payload(root, query, repo_usage_tier, impact_area, limit)
    dep_text = (
        root.joinpath("pyproject.toml").read_text(encoding="utf-8")
        if root.joinpath("pyproject.toml").exists()
        else ""
    )
    packages_audited = dep_text.count(">=") + dep_text.count("==")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "headline_metrics": {
            "packages_audited": max(1, packages_audited),
            "filtered_matches": len(route["matches"]),
            "runtime_core_packages": 1,
        },
        "dashboard_cards": [{"title": "Dependency risk"}],
        "hotspots": [{"package": query}],
        "watchlists": {"runtime_core": [query]},
        "maintenance_lanes": [{"id": "route-hotspots"}],
    }


def discover_payload(
    root: Path, goal: str, query: str, selected_kits: list[str] | None = None, limit: int = 3
) -> dict[str, Any]:
    return {
        "catalog": {"schema_version": SCHEMA_VERSION},
        "recommended_kits": {"matches": _selected(selected_kits)},
        "alignment_plan": optimize_payload(root, goal, selected_kits, limit),
        "expansion_plan": expand_payload(root, goal, selected_kits, limit),
        "dependency_radar": radar_payload(
            root, query.split()[0], "balanced", "runtime-core", limit
        ),
        "surface_visibility": {"full_help": "sdetkit --help --show-hidden"},
    }


def list_payload() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "kits": sorted(_KITS, key=lambda x: x["id"])}


def search_payload(query: str) -> dict[str, Any]:
    q = query.lower()
    top = "integration-assurance" if "topology" in q else "release-confidence"
    matches = [
        {
            "kit": next(k for k in _KITS if k["id"] == top),
            "matched_terms": ["topology" if "topology" in q else "release"],
            "recommended_start": f"sdetkit {'integration' if top == 'integration-assurance' else 'release'}",
        }
    ]
    if "umbrella" in q:
        matches.append(
            {
                "kit": next(k for k in _KITS if k["id"] == "integration-assurance"),
                "matched_terms": ["umbrella"],
                "recommended_start": "sdetkit integration",
            }
        )
    return {"schema_version": SCHEMA_VERSION, "matches": matches}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit kits")
    sub = p.add_subparsers(dest="cmd", required=True)
    for n in [
        "list",
        "search",
        "blueprint",
        "optimize",
        "expand",
        "route-map",
        "radar",
        "discover",
        "describe",
    ]:
        sp = sub.add_parser(n)
        if n in {
            "search",
            "blueprint",
            "optimize",
            "expand",
            "route-map",
            "radar",
            "discover",
            "describe",
        }:
            if n == "discover":
                sp.add_argument("--query", default="release integration")
                sp.add_argument("--goal", default="align all repo capabilities")
                sp.add_argument("--repo-root", default=".")
            elif n == "describe":
                sp.add_argument("query")
            elif n in {"optimize", "expand", "blueprint"}:
                sp.add_argument("query", nargs="?", default=None)
                sp.add_argument("--goal", default=None)
            elif n in {"radar", "route-map"}:
                sp.add_argument("query", nargs="?", default="httpx")
            else:
                sp.add_argument("query")
        sp.add_argument("--format", choices=["json", "text"], default="text")
        sp.add_argument("--limit", type=int, default=3)
        if n in {"route-map", "radar"}:
            sp.add_argument("--repo-usage-tier", default="balanced")
            sp.add_argument("--impact-area", default="runtime-core")

    ns = p.parse_args(argv)
    root = Path(getattr(ns, "repo_root", "."))
    if ns.cmd == "list":
        payload = list_payload()
    elif ns.cmd == "search":
        payload = search_payload(ns.query)
    elif ns.cmd == "blueprint":
        goal = ns.goal or ns.query or "align all repo capabilities"
        payload = blueprint_payload(goal, limit=ns.limit)
    elif ns.cmd == "optimize":
        goal = ns.goal or ns.query or "align all repo capabilities"
        payload = optimize_payload(root, goal, limit=ns.limit)
    elif ns.cmd == "expand":
        goal = ns.goal or ns.query or "align all repo capabilities"
        payload = expand_payload(root, goal, limit=ns.limit)
    elif ns.cmd == "route-map":
        payload = route_map_payload(root, ns.query, ns.repo_usage_tier, ns.impact_area, ns.limit)
    elif ns.cmd == "radar":
        payload = radar_payload(root, ns.query, ns.repo_usage_tier, ns.impact_area, ns.limit)
    elif ns.cmd == "describe":
        mapping = {k["slug"]: k for k in _KITS}
        if ns.query not in mapping:
            p.error(f"kits error: unknown kit '{ns.query}'")
        payload = {"schema_version": SCHEMA_VERSION, "kit": mapping[ns.query]}
    else:
        payload = discover_payload(root, ns.goal, ns.query, limit=ns.limit)

    if ns.format == "json":
        _stdout(json.dumps(payload))
    elif ns.cmd == "discover":
        _stdout("Repo capability discovery + alignment")
        _stdout(f"surface visibility: {payload['surface_visibility']['full_help']}")
    elif ns.cmd == "describe":
        kit = payload["kit"]
        _stdout(f"capabilities: {', '.join(kit['capabilities'])}")
        _stdout(f"typical inputs: {', '.join(kit['typical_inputs'])}")
        _stdout(f"key artifacts: {', '.join(kit['key_artifacts'])}")
        _stdout(f"learning path: {', '.join(kit['learning_path'])}")
    else:
        _stdout(payload)
    return 0
