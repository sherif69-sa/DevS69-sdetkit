from __future__ import annotations

import json
from pathlib import Path

from sdetkit.professional_naming_inventory import (
    AUTHORITY_BOUNDARY,
    SCHEMA_VERSION,
    build_professional_naming_inventory,
    write_professional_naming_inventory_artifact,
)


def test_professional_naming_inventory_detects_legacy_terms(tmp_path: Path) -> None:
    source = tmp_path / "src" / "sdetkit" / "phases" / "phase3_preplan.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'CHECK_ID = "phase2_" "hardening_quality_floor"\n',
        encoding="utf-8",
    )

    payload = build_professional_naming_inventory(root=tmp_path, terms=["phase2", "phase3"])

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "review required"
    assert payload["finding_count"] >= 2
    assert payload["rename_allowed"] is False
    assert payload["compatibility_required"] is True
    assert payload["by_term"]["phase2"] >= 1
    assert payload["by_term"]["phase3"] >= 1
    assert all(item["occurrence_count"] >= 1 for item in payload["items"])
    assert all("sample_lines" in item for item in payload["items"])


def test_professional_naming_inventory_classifies_docs_and_tests(tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "phase2-guide.md"
    tests = tmp_path / "tests" / "test_closeout_report.py"
    docs.parent.mkdir(parents=True)
    tests.parent.mkdir(parents=True)
    docs.write_text("phase2 rollout docs\n", encoding="utf-8")
    tests.write_text("def test_closeout_report():\n    assert True\n", encoding="utf-8")

    payload = build_professional_naming_inventory(root=tmp_path, terms=["phase2", "closeout"])

    classes = {item["classification"] for item in payload["items"]}
    assert "docs_only_cleanup" in classes
    assert "safe_cleanup_internal" in classes
    assert payload["by_surface"]["docs"] >= 1
    assert payload["by_surface"]["test"] >= 1
    assert payload["actionable_finding_count"] >= 1
    assert payload["review_first_finding_count"] >= 1


def test_professional_naming_inventory_preserves_non_authority_boundary(tmp_path: Path) -> None:
    file = tmp_path / "src" / "sdetkit" / "demo.py"
    file.parent.mkdir(parents=True)
    file.write_text('NAME = "demo"\n', encoding="utf-8")

    payload = build_professional_naming_inventory(root=tmp_path, terms=["demo"])

    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    for field, value in AUTHORITY_BOUNDARY.items():
        assert payload[field] is value
    for item in payload["items"]:
        for field, value in AUTHORITY_BOUNDARY.items():
            assert item[field] is value


def test_professional_naming_inventory_writes_artifact(tmp_path: Path) -> None:
    file = tmp_path / "README.md"
    out = tmp_path / "professional-naming-inventory.json"
    file.write_text("phase3 closeout\n", encoding="utf-8")

    payload = write_professional_naming_inventory_artifact(
        root=tmp_path,
        out=out,
        terms=["phase3", "closeout"],
    )

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == payload
    assert written["schema_version"] == SCHEMA_VERSION


def test_professional_naming_inventory_separates_actionable_prose_from_headings(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs" / "report.md"
    docs.parent.mkdir(parents=True)
    docs.write_text("# phase3 closeout\n\nphase3 rollout prose\n", encoding="utf-8")

    payload = build_professional_naming_inventory(root=tmp_path, terms=["phase3", "closeout"])

    by_actionability = payload["by_actionability"]
    assert by_actionability["actionable_prose_cleanup"] >= 1
    assert by_actionability["review_first_context"] >= 1
    assert payload["actionable_finding_count"] >= 1
    assert payload["review_first_finding_count"] >= 1
