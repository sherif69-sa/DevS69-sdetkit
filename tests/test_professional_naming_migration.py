from __future__ import annotations

import json
from pathlib import Path

from sdetkit.professional_naming_migration import (
    ALIAS_REQUIRED,
    MANUAL_REVIEW,
    PRESERVE_HISTORY,
    SAFE_CONTENT_REWRITE,
    TEMPLATE_LOCKED,
    build_professional_naming_migration_plan,
    main,
)


def _rename_map() -> dict:
    return {
        "schema_version": "sdetkit.professional_naming_rename_map.v1",
        "rename_map": {
            "phase3": "platform_readiness",
            "closeout": "completion_report",
            "demo": "example",
        },
    }


def test_professional_naming_migration_classifies_actionable_prose() -> None:
    inventory = {
        "items": [
            {
                "term": "demo",
                "path": "docs/guide.md",
                "match_type": "content",
                "classification": "docs_only_cleanup",
                "actionability": "actionable_prose_cleanup",
                "actionability_reason": "plain markdown prose",
            }
        ]
    }

    payload = build_professional_naming_migration_plan(inventory, _rename_map())

    assert payload["safe_content_rewrite_count"] == 1
    assert payload["recommended_next_action"] == "apply_safe_content_rewrite_first"
    item = payload["items"][0]
    assert item["migration_class"] == SAFE_CONTENT_REWRITE
    assert item["canonical_name"] == "example"
    assert item["allowed_to_apply"] is True


def test_professional_naming_migration_requires_alias_for_public_surface() -> None:
    inventory = {
        "items": [
            {
                "term": "phase3",
                "path": "src/sdetkit/cli.py",
                "match_type": "content",
                "classification": "public_surface_requires_alias",
                "actionability": "migration_or_alias_required",
                "actionability_reason": "compatibility plan required before changing this surface",
            }
        ]
    }

    payload = build_professional_naming_migration_plan(inventory, _rename_map())

    assert payload["alias_required_count"] == 1
    assert payload["recommended_next_action"] == "implement_aliases_before_rename"
    item = payload["items"][0]
    assert item["migration_class"] == ALIAS_REQUIRED
    assert item["allowed_to_apply"] is False


def test_professional_naming_migration_keeps_internal_wrapper_paths_review_first() -> None:
    inventory = {
        "items": [
            {
                "term": "phase3",
                "path": "src/sdetkit/phase3_kickoff.py",
                "match_type": "path",
                "classification": "internal_path_requires_migration",
                "actionability": "migration_or_alias_required",
                "actionability_reason": "compatibility plan required before changing this surface",
            }
        ]
    }

    payload = build_professional_naming_migration_plan(inventory, _rename_map())

    assert payload["alias_required_count"] == 0
    assert payload["manual_review_count"] == 1
    expected_next_action = "_".join(("review", "preserved", "history", "and", "manual", "contexts"))
    assert payload["recommended_next_action"] == expected_next_action
    item = payload["items"][0]
    assert item["migration_class"] == MANUAL_REVIEW
    assert item["allowed_to_apply"] is False
    assert item["required_guard"] == "human review before rename"


def test_professional_naming_migration_still_requires_alias_for_workflow_surface() -> None:
    inventory = {
        "items": [
            {
                "term": "phase3",
                "path": ".github/workflows/platform-readiness-quality-contract.yml",
                "match_type": "path",
                "classification": "workflow_alias_migration",
                "actionability": "migration_or_alias_required",
                "actionability_reason": "compatibility plan required before changing this surface",
            }
        ]
    }

    payload = build_professional_naming_migration_plan(inventory, _rename_map())

    assert payload["alias_required_count"] == 1
    assert payload["items"][0]["migration_class"] == ALIAS_REQUIRED
    assert payload["items"][0]["allowed_to_apply"] is False


def test_professional_naming_migration_preserves_history_headings() -> None:
    inventory = {
        "items": [
            {
                "term": "closeout",
                "path": "docs/roadmap/reports/history.md",
                "match_type": "content",
                "classification": "docs_only_cleanup",
                "actionability": "review_first_context",
                "actionability_reason": "heading_or_chronology_label",
            }
        ]
    }

    payload = build_professional_naming_migration_plan(inventory, _rename_map())

    assert payload["preserve_history_count"] == 1
    assert payload["items"][0]["migration_class"] == PRESERVE_HISTORY
    assert payload["items"][0]["allowed_to_apply"] is False


def test_professional_naming_migration_blocks_template_locked_docs() -> None:
    inventory = {
        "items": [
            {
                "term": "closeout",
                "path": "docs/integrations-release-prioritization-completion.md",
                "match_type": "content",
                "classification": "docs_only_cleanup",
                "actionability": "review_first_context",
                "actionability_reason": "template_locked_contract",
            }
        ]
    }

    payload = build_professional_naming_migration_plan(inventory, _rename_map())

    assert payload["template_locked_count"] == 1
    assert payload["items"][0]["migration_class"] == TEMPLATE_LOCKED
    assert payload["template_locked_rewrite"] is False


def test_professional_naming_migration_cli_writes_plan(tmp_path: Path, capsys) -> None:
    inventory_path = tmp_path / "inventory.json"
    rename_map_path = tmp_path / "rename-map.json"
    out_path = tmp_path / "migration-plan.json"

    inventory_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "term": "demo",
                        "path": "docs/guide.md",
                        "match_type": "content",
                        "classification": "docs_only_cleanup",
                        "actionability": "actionable_prose_cleanup",
                        "actionability_reason": "plain markdown prose",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    rename_map_path.write_text(json.dumps(_rename_map()), encoding="utf-8")

    rc = main(
        [
            "--inventory-json",
            str(inventory_path),
            "--rename-map",
            str(rename_map_path),
            "--out",
            str(out_path),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "migration_plan_json=" in stdout
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["safe_content_rewrite_count"] == 1
    assert payload["blind_rename_allowed"] is False
