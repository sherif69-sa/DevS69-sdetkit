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
    },
    {
        "id": "integration-assurance",
        "slug": "integration",
        "stability": "stable",
        "summary": "Offline-first service profile and environment readiness contracts.",
        "hero_commands": [
            "sdetkit integration check --profile integration-profile.json",
            "sdetkit integration matrix --profile integration-profile.json",
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
        print("hero commands:")
        for cmd in kit["hero_commands"]:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
