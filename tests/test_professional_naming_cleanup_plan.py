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
    REVIEW_LOCKED_NAMING_GOVERNANCE_REFERENCE,
    REVIEW_LOCKED_REFERENCE_COUNT,
    SAFE_INTERNAL,
    SCHEMA_VERSION,
    build_professional_naming_cleanup_plan,
    write_professional_naming_cleanup_plan_artifact,
)
from sdetkit.professional_naming_inventory import SCHEMA_VERSION as INVENTORY_SCHEMA_VERSION

COMPATIBILITY_REVIEW_FIRST_FINDING_COUNT = "_".join(
    ("compatibility", "review", "first", "finding", "count")
)


def _item(
    path: str,
    term: str,
    classification: str,
    occurrences: int = 1,
    actionability: str = "actionable_prose_cleanup",
) -> dict:
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
        "actionability": actionability,
        "actionability_reason": "test fixture",
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
    assert "compatibility_migration_" + "allowed=false" in result.stdout
    assert out.is_file()


def test_professional_naming_cleanup_plan_does_not_recommend_review_first_docs() -> None:
    item = _item(
        "docs/historical-report.md",
        "phase3",
        DOCS_ONLY,
        actionability="review_first_context",
    )
    inventory = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "status": "review required",
        "finding_count": 1,
        "items": [item],
    }

    payload = build_professional_naming_cleanup_plan(inventory)

    assert payload["recommended_first_slice"] is None
    assert payload["actionable_finding_count"] == 0
    assert payload["review_first_finding_count"] == 1
    assert payload["cleanup_slices"][0]["safe_to_plan_first"] is False


def test_professional_naming_cleanup_plan_separates_compatibility_review_first_findings() -> None:
    item = _item(
        "src/sdetkit/cli.py",
        "phase3",
        PUBLIC_ALIAS,
        actionability="migration_or_alias_required",
    )
    item["actionability_reason"] = "compatibility plan required before changing this surface"
    inventory = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "status": "review required",
        "finding_count": 1,
        "items": [item],
    }

    payload = build_professional_naming_cleanup_plan(inventory)

    assert payload["actionable_finding_count"] == 0
    assert payload["review_first_finding_count"] == 1
    assert payload[COMPATIBILITY_REVIEW_FIRST_FINDING_COUNT] == 1
    assert payload["recommended_first_slice"] is None
    assert payload["actionability_mix"] == [{"name": "migration_or_alias_required", "count": 1}]
    assert payload["review_first_reason_mix"] == [
        {
            "name": "compatibility plan required before changing this surface",
            "count": 1,
        }
    ]

    cleanup_slice = payload["cleanup_slices"][0]
    assert cleanup_slice["classification"] == PUBLIC_ALIAS
    assert cleanup_slice["requires_compatibility_plan"] is True
    assert cleanup_slice["safe_to_plan_first"] is False
    assert cleanup_slice[COMPATIBILITY_REVIEW_FIRST_FINDING_COUNT] == 1
    assert cleanup_slice["actionability_mix"] == [
        {"name": "migration_or_alias_required", "count": 1}
    ]
    assert cleanup_slice["review_first_reason_mix"] == [
        {
            "name": "compatibility plan required before changing this surface",
            "count": 1,
        }
    ]


def test_professional_naming_cleanup_plan_counts_review_locked_references() -> None:
    item = _item(
        "docs/professional-naming-debt-register.md",
        "closeout",
        DOCS_ONLY,
        actionability="review_first_context",
    )
    item["actionability_reason"] = REVIEW_LOCKED_NAMING_GOVERNANCE_REFERENCE
    inventory = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "status": "review required",
        "finding_count": 1,
        "items": [item],
    }

    payload = build_professional_naming_cleanup_plan(inventory)

    assert payload["actionable_finding_count"] == 0
    assert payload["review_first_finding_count"] == 1
    assert payload[REVIEW_LOCKED_REFERENCE_COUNT] == 1
    assert payload["recommended_first_slice"] is None
    assert payload["review_first_reason_mix"] == [
        {"name": REVIEW_LOCKED_NAMING_GOVERNANCE_REFERENCE, "count": 1}
    ]

    cleanup_slice = payload["cleanup_slices"][0]
    assert cleanup_slice["classification"] == DOCS_ONLY
    assert cleanup_slice["safe_to_plan_first"] is False
    assert cleanup_slice[REVIEW_LOCKED_REFERENCE_COUNT] == 1
    assert cleanup_slice["review_first_reason_mix"] == [
        {"name": REVIEW_LOCKED_NAMING_GOVERNANCE_REFERENCE, "count": 1}
    ]
