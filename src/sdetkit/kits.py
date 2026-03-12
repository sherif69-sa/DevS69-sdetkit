from __future__ import annotations

import argparse
import json
import sys
from typing import Final

from .atomicio import canonical_json_dumps

SCHEMA_VERSION: Final[str] = "sdetkit.kits.catalog.v1"

_KITS: Final[list[dict[str, object]]] = [
    {
        "id": "release-confidence",
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
        "stability": "stable",
        "summary": "Offline-first service profile and environment readiness contracts.",
        "hero_commands": [
            "sdetkit integration check --profile integration-profile.json",
            "sdetkit integration matrix --profile integration-profile.json",
        ],
    },
    {
        "id": "failure-forensics",
        "stability": "experimental",
        "summary": "Run comparison and deterministic repro bundle generation.",
        "hero_commands": [
            "sdetkit forensics compare --from old.json --to new.json",
            "sdetkit forensics bundle --run run.json --output bundle.zip",
        ],
    },
]


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
    parser.add_argument("action", nargs="?", default="list", choices=["list"])
    parser.add_argument("--format", choices=["json", "text"], default="text")
    ns = parser.parse_args(argv)

    payload = list_payload()
    if ns.format == "json":
        sys.stdout.write(canonical_json_dumps(payload))
        return 0

    print("SDETKit umbrella kits")
    for kit in payload["kits"]:
        assert isinstance(kit, dict)
        print(f"- {kit['id']} [{kit['stability']}]")
        print(f"  {kit['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
