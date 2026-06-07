from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ROOT / "docs" / "naming" / "artifact-report-path-aliases.json"


def test_artifact_report_path_alias_registry_is_valid() -> None:
    payload = json.loads(ALIASES.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.naming.artifact-report-path-aliases.v1"
    assert payload["alias_count"] == len(payload["aliases"])
    assert payload["alias_count"] > 0


def test_professional_artifact_report_paths_exist_without_removing_legacy_paths() -> None:
    payload = json.loads(ALIASES.read_text(encoding="utf-8"))

    for item in payload["aliases"]:
        legacy = ROOT / item["legacy_path"]
        professional = ROOT / item["professional_path"]

        assert legacy.exists(), item
        assert professional.exists(), item
        assert legacy != professional
