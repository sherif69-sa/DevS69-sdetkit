from __future__ import annotations

import re
import subprocess
import sys

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


def test_root_help_avoids_legacy_tier_labels() -> None:
    proc = _run("--help")
    assert proc.returncode == 0
    assert "Stable/Core" not in proc.stdout
    assert "Stable/Compatibility" not in proc.stdout


def test_boost_help_discoverability() -> None:
    proc = _run("boost", "--help")
    assert proc.returncode == 0
    assert "scan" in proc.stdout


def test_boost_scan_help_discoverability() -> None:
    proc = _run("boost", "scan", "--help")
    assert proc.returncode == 0
    assert "--minutes" in proc.stdout
    assert "--max-lines" in proc.stdout
    assert "--deep" in proc.stdout
    assert "--learn" in proc.stdout
    assert "--db" in proc.stdout
    assert "--index-out" in proc.stdout
    assert "--evidence-dir" in proc.stdout


def test_index_help_discoverability() -> None:
    proc = _run("index", "--help")
    assert proc.returncode == 0
    assert "build" in proc.stdout
    assert "inspect" in proc.stdout


def test_patch_workbench_help_discoverability() -> None:
    proc = _run("patch", "workbench", "--help")
    assert proc.returncode == 0
    assert "--from-release-room" in proc.stdout
    assert "--max-candidates" in proc.stdout
