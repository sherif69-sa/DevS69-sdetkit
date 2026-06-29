from __future__ import annotations

import json
from pathlib import Path

from sdetkit.public_surface_contract import render_root_help_groups

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "src" / "sdetkit" / "public_command_surface.json"


def test_root_help_keeps_canonical_path_and_hides_detailed_inventory() -> None:
    rendered = render_root_help_groups()

    assert "gate fast -> gate release -> doctor" in rendered
    assert "python -m sdetkit gate fast" in rendered
    assert "python -m sdetkit gate release" in rendered
    assert "python -m sdetkit doctor" in rendered
    assert "umbrella kits [Advanced but supported]" in rendered
    assert "Experimental / incubator" in rendered
    assert "legacy" in rendered
    assert "supporting utilities and automation [" not in rendered
    assert "weekly-review" not in rendered
    assert "first-contribution" not in rendered
    assert "demo" not in rendered


def test_public_command_surface_declares_small_first_run_contract() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["contract_version"] == 2
    assert contract["public_stable_front_door_commands"] == ["gate", "doctor", "release"]
    assert len(contract["canonical_first_path"]) == 3
    assert contract["root_help_contract"] == {
        "detailed_family_inventory": False,
        "show_canonical_path": True,
        "show_policy_tiers": True,
        "show_compatibility_namespace": True,
        "advanced_inventory_command": "python -m sdetkit kits list",
        "experimental_inventory_location": "docs/command-surface.md",
    }


def test_public_command_surface_limits_primary_make_and_docs_journeys() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["primary_make_targets"] == [
        "install",
        "merge-ready",
        "first-proof",
        "package-validate",
        "release-preflight",
    ]
    journeys = contract["primary_documentation_journeys"]
    assert [journey["id"] for journey in journeys] == [
        "install_and_decide",
        "investigate_failure",
        "adopt_ci",
        "reference",
    ]
    assert all((ROOT / journey["entry"]).is_file() for journey in journeys)
