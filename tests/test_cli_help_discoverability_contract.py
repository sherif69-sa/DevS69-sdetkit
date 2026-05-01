from __future__ import annotations

import json
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
    assert "command discovery (stability-aware)" in normalized
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


def test_root_help_exposes_legacy_namespace_but_hides_legacy_lanes() -> None:
    proc = _run("--help")
    assert proc.returncode == 0
    assert "legacy" in proc.stdout
    assert "weekly-review-lane" not in proc.stdout
    assert "phase1-hardening" not in proc.stdout


def test_legacy_namespace_routes_to_legacy_commands() -> None:
    proc = _run("legacy", "weekly-review-lane", "--help")
    assert proc.returncode == 0
    assert "usage:" in proc.stdout.lower()


def test_legacy_namespace_lists_contained_legacy_commands() -> None:
    proc = _run("legacy", "list")
    assert proc.returncode == 0
    listed = set(proc.stdout.splitlines())
    assert "weekly-review-lane" in listed
    assert "phase1-hardening" in listed
    assert "optimization-closeout-foundation" in listed


def test_legacy_namespace_migrate_hint_renders_recommendation() -> None:
    proc = _run("legacy", "migrate-hint", "phase1-hardening")
    assert proc.returncode == 0
    assert "[legacy-hint]" in proc.stdout
    assert "phase1-hardening" in proc.stdout
    assert "Deprecation horizon:" in proc.stdout
    assert "gate fast -> gate release -> doctor" in proc.stdout


def test_legacy_namespace_migrate_hint_requires_command_name() -> None:
    proc = _run("legacy", "migrate-hint")
    assert proc.returncode == 2
    assert "expected command name after migrate-hint" in proc.stderr.lower()


def test_legacy_namespace_migrate_hint_json_format() -> None:
    proc = _run("legacy", "migrate-hint", "--format", "json", "phase1-hardening")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "1"
    assert payload["mode"] == "single"
    assert payload["command"] == "phase1-hardening"
    assert payload["preferred_surface"] == "python -m sdetkit playbooks --help"
    assert "deprecation_horizon" in payload
    assert payload["canonical_path"] == ["gate fast", "gate release", "doctor"]
    assert "legacy-hint" in payload["hint"]


def test_legacy_namespace_migrate_hint_all_json_format() -> None:
    proc = _run("legacy", "migrate-hint", "--all", "--format", "json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "1"
    assert payload["mode"] == "all"
    assert payload["count"] >= 1
    assert isinstance(payload["items"], list)
    first = payload["items"][0]
    assert "command" in first
    assert "preferred_surface" in first
    assert "deprecation_horizon" in first
    assert "hint" in first


def test_legacy_namespace_migrate_hint_rejects_command_and_all_together() -> None:
    proc = _run("legacy", "migrate-hint", "--all", "phase1-hardening")
    assert proc.returncode == 2
    assert "use either <command> or --all" in proc.stderr.lower()


def test_policy_tier_vocabulary_matches_public_contract_and_docs() -> None:
    contract_help = render_root_help_groups()
    docs_text = Path("docs/stability-levels.md").read_text(encoding="utf-8")

    for tier in POLICY_TIERS:
        assert tier in contract_help
        assert tier in docs_text


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


def test_release_room_help_discoverability() -> None:
    proc = _run("release-room", "--help")
    assert proc.returncode == 0
    assert "plan" in proc.stdout


def test_release_room_plan_help_discoverability() -> None:
    proc = _run("release-room", "plan", "--help")
    assert proc.returncode == 0
    assert "--max-lines" in proc.stdout
    assert "--evidence-dir" in proc.stdout
