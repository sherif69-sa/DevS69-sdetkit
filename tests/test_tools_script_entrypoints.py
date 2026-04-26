from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_help(script_rel: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / script_rel), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_triage_script_help_entrypoint() -> None:
    proc = _run_help("tools/triage.py")
    assert proc.returncode == 0
    assert "usage:" in proc.stdout


def test_render_public_surface_script_help_entrypoint() -> None:
    proc = _run_help("tools/render_public_surface_contract_table.py")
    assert proc.returncode == 0
    assert "usage:" in proc.stdout


def test_patch_harness_script_help_entrypoint() -> None:
    proc = _run_help("tools/patch_harness.py")
    assert proc.returncode == 0
    assert "usage:" in proc.stdout
