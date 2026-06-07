from __future__ import annotations

import json
from pathlib import Path

from sdetkit.schema_version_aliases import (
    SCHEMA_VERSION_ALIASES,
    accepted_schema_versions,
    legacy_schema_version,
    professional_schema_version,
    schema_versions_compatible,
)

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ROOT / "docs" / "naming" / "schema-version-aliases.json"


def test_schema_version_alias_registry_matches_docs() -> None:
    payload = json.loads(ALIASES.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.naming.schema-version-aliases.v1"
    assert payload["alias_count"] == len(payload["aliases"])
    assert payload["alias_count"] > 0

    documented = {item["legacy"]: item["professional"] for item in payload["aliases"]}

    assert documented == SCHEMA_VERSION_ALIASES


def test_professional_schema_versions_are_compatibility_aliases() -> None:
    for legacy, professional in SCHEMA_VERSION_ALIASES.items():
        assert professional_schema_version(legacy) == professional
        assert legacy_schema_version(professional) == legacy
        assert schema_versions_compatible(legacy, professional)
        assert schema_versions_compatible(professional, legacy)
        assert legacy in accepted_schema_versions(legacy)
        assert professional in accepted_schema_versions(legacy)


def test_unknown_schema_version_is_stable() -> None:
    unknown = "sdetkit.unrelated-contract.v1"

    assert professional_schema_version(unknown) == unknown
    assert legacy_schema_version(unknown) == unknown
    assert accepted_schema_versions(unknown) == (unknown,)
    assert schema_versions_compatible(unknown, unknown)
