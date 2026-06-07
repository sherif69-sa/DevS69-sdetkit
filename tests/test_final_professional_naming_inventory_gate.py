from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "naming" / "final-professional-naming-inventory.json"
SUMMARY = ROOT / "docs" / "naming" / "final-professional-naming-inventory.md"

REVIEW_FIRST_ACTIONABILITIES = {
    "review_first_context",
    "internal_cleanup_review_first",
}

COMPATIBILITY_ACTIONABILITIES = {
    "migration_or_alias_required",
}

COMPATIBILITY_CLASSIFICATIONS = {
    "internal_path_requires_migration",
    "public_surface_requires_alias",
    "workflow_alias_migration",
}

EVIDENCE_PREFIXES = (
    ".docs/",
    "docs/artifacts/",
    "docs/contracts/",
    "docs/naming/",
    "docs/reports/",
    "docs/roadmap/reports/",
    "tools/",
)

EVIDENCE_FILES = {
    "CHANGELOG.md",
    "index.md",
    "mkdocs.yml",
    "docs/roadmap/manifest.json",
}

COMPATIBILITY_PREFIXES = (
    "src/sdetkit/_legacy_cli.py",
    "src/sdetkit/agent/demo.py",
    "src/sdetkit/demo",
    "src/sdetkit/phase",
    "src/sdetkit/phases/phase",
    "src/sdetkit/cli/playbooks_cli.py",
    "src/sdetkit/legacy_adapters/",
)


def _payload() -> dict[str, object]:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def _is_evidence_path(path: str) -> bool:
    return path in EVIDENCE_FILES or path.startswith(EVIDENCE_PREFIXES)


def _is_compatibility_path(path: str) -> bool:
    return path.startswith(COMPATIBILITY_PREFIXES)


def _is_required_workflow_context(item: dict[str, object]) -> bool:
    path = item.get("path")
    term = item.get("term")
    classification = item.get("classification")

    if (
        path == ".github/workflows/ci.yml"
        and term == "temp"
        and classification == "workflow_alias_migration"
    ):
        return True

    return (
        path == ".github/workflows/platform-readiness-quality-contract.yml"
        and term in {"phase1", "phase3"}
        and classification == "workflow_alias_migration"
    )


def _is_approved_remaining_item(item: dict[str, object]) -> bool:
    actionability = str(item.get("actionability", ""))
    classification = str(item.get("classification", ""))
    path = str(item.get("path", ""))

    if _is_required_workflow_context(item):
        return True

    if actionability in REVIEW_FIRST_ACTIONABILITIES:
        return True

    if _is_evidence_path(path):
        return True

    if (
        actionability in COMPATIBILITY_ACTIONABILITIES
        and classification in COMPATIBILITY_CLASSIFICATIONS
        and _is_compatibility_path(path)
    ):
        return True

    return False


def test_final_professional_naming_inventory_files_exist() -> None:
    assert INVENTORY.exists()
    assert SUMMARY.exists()


def test_final_professional_naming_inventory_has_no_unapproved_active_debt() -> None:
    payload = _payload()
    items = payload.get("items", [])

    unapproved = [
        item for item in items if isinstance(item, dict) and not _is_approved_remaining_item(item)
    ]

    assert unapproved == []


def test_final_professional_naming_inventory_records_review_first_debt() -> None:
    payload = _payload()

    assert payload["finding_count"] >= payload["review_first_finding_count"]
    assert payload["review_first_finding_count"] > 0
