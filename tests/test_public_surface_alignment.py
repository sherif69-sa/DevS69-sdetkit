from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from sdetkit.public_surface_contract import (
    load_public_command_surface_contract,
    render_root_help_groups,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"
PUBLIC_COMMAND_CONTRACT = REPO_ROOT / "src" / "sdetkit" / "public_command_surface.json"


def test_public_surface_alignment_script_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/check_public_surface_alignment.py"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "public-surface-alignment check passed" in proc.stdout


def test_public_command_surface_contract_is_machine_readable_and_stable() -> None:
    contract = load_public_command_surface_contract()
    assert contract == json.loads(PUBLIC_COMMAND_CONTRACT.read_text(encoding="utf-8"))
    assert contract["contract_version"] == 1
    assert contract["canonical_first_path"] == [
        "python -m sdetkit gate fast",
        "python -m sdetkit gate release",
        "python -m sdetkit doctor",
    ]
    assert contract["public_stable_front_door_commands"] == ["gate", "doctor", "release"]
    assert contract["advanced_supported_next_step"] == "python -m sdetkit kits list"


def test_root_help_groups_include_machine_readable_contract_commands() -> None:
    contract = load_public_command_surface_contract()
    help_groups = render_root_help_groups()
    for command in contract["public_stable_front_door_commands"]:
        assert command in help_groups
    assert "gate fast -> gate release -> doctor" in help_groups
    assert contract["advanced_supported_next_step"] in help_groups


def test_pages_workflow_enforces_alignment_check_before_mkdocs_build() -> None:
    workflow = yaml.safe_load(PAGES_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    run_steps = [step.get("run", "") for step in steps if isinstance(step, dict)]
    command_blob = "\n".join(run_steps)

    assert "python scripts/check_public_surface_alignment.py" in command_blob
    assert "python -m mkdocs build --strict" in command_blob
    assert command_blob.index(
        "python scripts/check_public_surface_alignment.py"
    ) < command_blob.index("python -m mkdocs build --strict")


def test_mkdocs_nav_demotes_archive_to_last_section() -> None:
    text = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav_block = text.split("\nnav:\n", 1)[1].split("\nexclude_docs:", 1)[0]
    labels = [
        match.group(1)
        for line in nav_block.splitlines()
        if (match := re.match(r"^  - ([^:]+):", line))
    ]

    assert labels[:3] == [
        "Start here",
        "Canonical first-proof path (primary)",
        "Team adoption and CI rollout (primary)",
    ]
    assert "Current reference and discoverability (secondary)" in labels
    assert labels[-1] == "Historical archive (non-primary)"
