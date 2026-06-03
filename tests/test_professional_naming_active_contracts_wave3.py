from __future__ import annotations

from sdetkit.legacy_adapters import LEGACY_COMMAND_MODULES
from sdetkit.legacy_adapters.foundation import (
    CANONICAL_FOUNDATION_COMMAND_MODULES,
    LEGACY_FOUNDATION_COMMAND_MODULES,
)
from sdetkit.phases import baseline_hardening, baseline_wrap, release_readiness_kickoff


def test_canonical_foundation_commands_are_registered() -> None:
    expected = {
        "baseline-hardening": "sdetkit.baseline_hardening",
        "baseline-wrap": "sdetkit.baseline_wrap",
        "release-readiness-kickoff": "sdetkit.release_readiness_kickoff",
        "example-asset": "sdetkit.example_asset",
        "example-asset2": "sdetkit.example_asset2",
    }

    assert CANONICAL_FOUNDATION_COMMAND_MODULES == expected
    for command, module in expected.items():
        assert LEGACY_COMMAND_MODULES[command] == module


def test_legacy_foundation_commands_still_resolve_to_canonical_modules() -> None:
    expected = {
        "phase1-hardening": "sdetkit.baseline_hardening",
        "phase1-wrap": "sdetkit.baseline_wrap",
        "phase2-kickoff": "sdetkit.release_readiness_kickoff",
        "demo-asset": "sdetkit.example_asset",
        "demo-asset2": "sdetkit.example_asset2",
    }

    for command, module in expected.items():
        assert LEGACY_FOUNDATION_COMMAND_MODULES[command] == module
        assert LEGACY_COMMAND_MODULES[command] == module


def test_baseline_hardening_active_contract_uses_canonical_names() -> None:
    text = baseline_hardening._DEFAULT_PAGE_TEMPLATE

    assert baseline_hardening._CANONICAL_LANE_NAME == "baseline-hardening"
    assert baseline_hardening._CANONICAL_PACK_DIR == "docs/artifacts/baseline-hardening-pack"
    assert baseline_hardening._CANONICAL_SUMMARY_JSON == "baseline-hardening-summary.json"
    assert "baseline-hardening --format json --strict" in text
    assert "Phase-1 hardening" not in text
    assert "phase1-hardening" not in text


def test_baseline_wrap_active_contract_uses_canonical_names() -> None:
    cfg = baseline_wrap._CFG
    text = cfg["page_template"]

    assert cfg["name"] == "baseline-wrap"
    assert cfg["page_path"] == "docs/integrations-baseline-wrap.md"
    assert cfg["summary_json"] == "baseline-wrap-summary.json"
    assert cfg["summary_md"] == "baseline-wrap-summary.md"
    assert "baseline-wrap-release-readiness-backlog.md" in cfg["pack_files"]
    assert "Baseline wrap" in text
    assert "Phase-1 wrap" not in text
    assert "phase1-wrap" not in str(cfg)


def test_release_readiness_kickoff_active_contract_uses_canonical_names() -> None:
    cfg = release_readiness_kickoff._CFG
    text = cfg["page_template"]

    assert cfg["name"] == "release-readiness-kickoff"
    assert cfg["page_path"] == "docs/integrations-release-readiness-kickoff.md"
    assert cfg["summary_json"] == "release-readiness-kickoff-summary.json"
    assert cfg["summary_md"] == "release-readiness-kickoff-summary.md"
    assert "release-readiness-kickoff-delivery-board.md" in cfg["pack_files"]
    assert "Release readiness kickoff" in text
    assert "Phase-2 kickoff" not in text
    assert "phase2-kickoff" not in str(cfg)
