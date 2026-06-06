from __future__ import annotations

from pathlib import Path

from sdetkit.professional_naming_inventory import build_professional_naming_inventory


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _single_item(root: Path, path: str, content: str) -> dict[str, object]:
    _write(root / path, content)

    inventory = build_professional_naming_inventory(root=root)
    items = inventory["items"]

    assert len(items) == 1
    return dict(items[0])


def test_plain_markdown_legacy_wording_remains_actionable_prose(tmp_path: Path) -> None:
    item = _single_item(
        tmp_path,
        "docs/operator-guide.md",
        "This closeout language should become completion language.\n",
    )

    assert item["classification"] == "docs_only_cleanup"
    assert item["actionability"] == "actionable_prose_cleanup"
    assert item["actionability_reason"] == "plain markdown prose"


def test_naming_governance_docs_are_review_locked_references(tmp_path: Path) -> None:
    item = _single_item(
        tmp_path,
        "docs/professional-naming-debt-register.md",
        "This register tracks closeout compatibility wording.\n",
    )

    assert item["classification"] == "docs_only_cleanup"
    assert item["actionability"] == "review_first_context"
    assert item["actionability_reason"] == "review_locked_naming_governance_reference"


def test_rename_map_is_review_locked_even_when_content_is_plain(tmp_path: Path) -> None:
    item = _single_item(
        tmp_path,
        "docs/naming/professional-naming-rename-map.json",
        '{"legacy": "phase3", "preferred": "platform-readiness"}\n',
    )

    assert item["classification"] == "docs_only_cleanup"
    assert item["actionability"] == "review_first_context"
    assert item["actionability_reason"] == "review_locked_naming_governance_reference"


def test_source_public_surface_still_requires_migration_plan(tmp_path: Path) -> None:
    item = _single_item(
        tmp_path,
        "src/sdetkit/cli.py",
        "HELP = 'phase3 compatibility command'\n",
    )

    assert item["classification"] == "public_surface_requires_alias"
    assert item["actionability"] == "migration_or_alias_required"
    assert item["requires_compatibility_plan"] is True
