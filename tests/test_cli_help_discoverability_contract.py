from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from sdetkit.public_surface_contract import render_root_help_groups


POLICY_TIERS = (
    "Public / stable",
    "Advanced but supported",
    "Experimental / incubator",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True)


def _normalize(text: str) -> str:
    """Normalize help/doc text for robust contains checks across wrapping changes."""
    return re.sub(r"\s+", " ", text).strip().lower()


def test_root_help_exposes_canonical_first_time_path() -> None:
    proc = _run("--help")
    assert proc.returncode == 0
    normalized = _normalize(proc.stdout)

    canonical_markers = (
        "python -m sdetkit gate fast",
        "python -m sdetkit gate release",
        "python -m sdetkit doctor",
    )
    for marker in canonical_markers:
        assert marker in normalized

    assert "release confidence canonical path" in normalized
    assert "umbrella kits [advanced but supported] (use first: no;" in normalized


def test_root_help_includes_policy_tier_vocabulary() -> None:
    proc = _run("--help")
    assert proc.returncode == 0

    for tier in POLICY_TIERS:
        assert tier in proc.stdout


def test_root_help_avoids_legacy_tier_labels() -> None:
    proc = _run("--help")
    assert proc.returncode == 0
    assert "Stable/Core" not in proc.stdout
    assert "Stable/Compatibility" not in proc.stdout


def test_policy_tier_vocabulary_matches_public_contract_and_docs() -> None:
    contract_help = render_root_help_groups()
    docs_text = Path("docs/stability-levels.md").read_text(encoding="utf-8")

    for tier in POLICY_TIERS:
        assert tier in contract_help
        assert tier in docs_text
