from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit.professional_naming_cleanup_plan import (
    ACTION_BOUNDARY,
    AUTHORITY_BOUNDARY,
    DOCS_ONLY,
    PUBLIC_ALIAS,
    SAFE_INTERNAL,
    SCHEMA_VERSION,
    build_professional_naming_cleanup_plan,
    write_professional_naming_cleanup_plan_artifact,
)
from sdetkit.professional_naming_inventory import SCHEMA_VERSION as INVENTORY_SCHEMA_VERSION


def _item(path: str, term: str, classification: str, occurrences: int = 1) -> dict:
    return {
        "path": path,
        "line": 1,
        "sample_lines": [1],
        "occurrence_count": occurrences,
        "surface": "docs" if path.endswith(".md") else "source",
        "match_type": "content",
        "term": term,
        "classification": classification,
        "replacement_hint": "production name",
        "requires_compatibility_plan": classification == PUBLIC_ALIAS,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _inventory() -> dict:
    items = [
        _item("docs/legacy.md", "closeout", DOCS_ONLY, 3),
        _item("src/sdetkit/internal.py", "demo", SAFE_INTERNAL, 2),
        _item("src/sdetkit/cli.py", "demo", PUBLIC_ALIAS, 1),
    ]
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "status": "review required",
        "finding_count": len(items),
        "items": items,
    }


def test_professional_naming_cleanup_plan_prioritizes_safe_slices() -> None:
    payload = build_professional_naming_cleanup_plan(_inventory())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "plan review required"
    assert payload["slice_count"] == 3
    assert payload["recommended_first_slice"] == DOCS_ONLY.replace("_", "-")
    assert payload["safe_slice_count"] == 2
    assert payload["compatibility_slice_count"] == 1

    first = payload["cleanup_slices"][0]
    assert first["classification"] == DOCS_ONLY
    assert first["safe_to_plan_first"] is True
    assert first["rename_allowed"] is False


def test_professional_naming_cleanup_plan_blocks_rename_authority() -> None:
    payload = build_professional_naming_cleanup_plan(_inventory())

    for field, value in ACTION_BOUNDARY.items():
        assert payload[field] is value
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    for cleanup_slice in payload["cleanup_slices"]:
        for field, value in ACTION_BOUNDARY.items():
            assert cleanup_slice[field] is value
        for field, value in AUTHORITY_BOUNDARY.items():
            assert cleanup_slice[field] is value


def test_professional_naming_cleanup_plan_handles_clean_inventory() -> None:
    payload = build_professional_naming_cleanup_plan(
        {
            "schema_version": INVENTORY_SCHEMA_VERSION,
            "status": "clean",
            "finding_count": 0,
            "items": [],
        }
    )

    assert payload["status"] == "clean"
    assert payload["slice_count"] == 0
    assert payload["recommended_first_slice"] is None
    assert payload["cleanup_slices"] == []


def test_professional_naming_cleanup_plan_writes_artifact(tmp_path: Path) -> None:
    inventory_path = tmp_path / "professional-naming-inventory.json"
    out = tmp_path / "professional-naming-cleanup-plan.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")

    payload = write_professional_naming_cleanup_plan_artifact(
        inventory_json=inventory_path,
        out=out,
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION


def test_professional_naming_cleanup_plan_cli_round_trip(tmp_path: Path) -> None:
    inventory_path = tmp_path / "professional-naming-inventory.json"
    out = tmp_path / "professional-naming-cleanup-plan.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "professional-naming-cleanup-plan",
            "--inventory-json",
            str(inventory_path),
            "--out",
            str(out),
            "--format",
            "text",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "cleanup_plan_json=" in result.stdout
    assert "rename_allowed=false" in result.stdout
    assert "compatibility_migration_allowed=false" in result.stdout
    assert out.is_file()
