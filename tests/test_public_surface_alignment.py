from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"


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


def test_pages_workflow_enforces_alignment_check_before_mkdocs_build() -> None:
    workflow = yaml.safe_load(PAGES_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    run_steps = [step.get("run", "") for step in steps if isinstance(step, dict)]
    command_blob = "\n".join(run_steps)

    assert "python scripts/check_public_surface_alignment.py" in command_blob
    assert "python -m mkdocs build --strict" in command_blob
    assert command_blob.index("python scripts/check_public_surface_alignment.py") < command_blob.index(
        "python -m mkdocs build --strict"
    )


def test_mkdocs_nav_demotes_archive_to_last_section() -> None:
    text = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav_block = text.split("\nnav:\n", 1)[1].split("\nexclude_docs:", 1)[0]
    labels = [
        match.group(1) for line in nav_block.splitlines() if (match := re.match(r"^  - ([^:]+):", line))
    ]

    assert labels[:3] == [
        "Start here",
        "Canonical first-proof path (primary)",
        "Team adoption and CI rollout (primary)",
    ]
    assert "Current reference and discoverability (secondary)" in labels
    assert labels[-1] == "Historical archive (non-primary)"
