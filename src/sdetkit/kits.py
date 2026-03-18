from __future__ import annotations

import argparse
import sys
from typing import Final, TypedDict

from .atomicio import canonical_json_dumps

SCHEMA_VERSION: Final[str] = "sdetkit.kits.catalog.v1"


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
        ],
        "capabilities": [
            "Flake and failure classification",
            "Change impact summaries",
            "Environment capture for reproducibility",
            "Signal shaping for quality governance",
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
        ],
        "learning_path": [
            "sdetkit intelligence capture-env",
            "sdetkit intelligence flake classify --history history.json",
            "sdetkit intelligence impact summarize --changed changed.txt --map testmap.json",
        ],
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


def list_payload() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kits": sorted(_KITS, key=lambda item: str(item["id"])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit kits",
        description="Discover umbrella kit surfaces and stability lanes.",
    )
    parser.add_argument("action", nargs="?", default="list", choices=["list", "describe"])
    parser.add_argument("kit", nargs="?", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    ns = parser.parse_args(argv)

    if ns.action == "describe":
        if not ns.kit:
            sys.stderr.write("kits error: expected <kit> for `sdetkit kits describe <kit>`\n")
            return 2
        kit = _resolve_kit(str(ns.kit))
        if kit is None:
            sys.stderr.write(f"kits error: unknown kit '{ns.kit}'\n")
            return 2
        payload = {"schema_version": SCHEMA_VERSION, "kit": kit}
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
            return 0
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
        return 0

    if ns.kit:
        sys.stderr.write("kits error: unexpected <kit> for list action\n")
        return 2

    kits_sorted = sorted(_KITS, key=lambda item: item["id"])
    list_json_payload = {
        "schema_version": SCHEMA_VERSION,
        "kits": kits_sorted,
    }
    if ns.format == "json":
        sys.stdout.write(canonical_json_dumps(list_json_payload))
        return 0

    print("SDETKit umbrella kits")
    for kit in kits_sorted:
        print(f"- {kit['id']} [{kit['stability']}]")
        print(f"  {kit['summary']}")
        print(f"  capabilities: {', '.join(kit['capabilities'])}")
        print(f"  start with: {kit['learning_path'][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
