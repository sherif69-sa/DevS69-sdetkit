from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "docs" / "naming" / "active-wording-sweep.json"


def test_active_wording_sweep_registry_is_documented() -> None:
    payload = json.loads(SWEEP.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.naming.active-wording-sweep.v1"
    assert payload["changed_file_count"] == len(payload["changed_files"])
    assert payload["changed_file_count"] > 0


def test_active_wording_sweep_does_not_touch_excluded_surfaces() -> None:
    payload = json.loads(SWEEP.read_text(encoding="utf-8"))

    excluded_prefixes = (
        "docs/artifacts/",
        "docs/contracts/",
        "docs/roadmap/reports/",
        "docs/reports/",
    )

    for item in payload["changed_files"]:
        path = item["path"]
        assert not path.startswith(excluded_prefixes), path
