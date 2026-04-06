from __future__ import annotations

from pathlib import Path

from sdetkit.roadmap_manifest import _next_closeout_calls, build_manifest, check_manifest


def test_roadmap_manifest_is_fresh() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ok = check_manifest(repo_root=repo_root)
    assert ok, "docs/roadmap/manifest.json is stale; run: python -m sdetkit.roadmap_manifest write"


def test_roadmap_manifest_includes_closeout_alignment_inventory() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = build_manifest(repo_root=repo_root)
    alignment = manifest.get("closeout_alignment")
    assert isinstance(alignment, dict)
    assert int(alignment.get("count", 0)) >= 1
    assert isinstance(alignment.get("entries"), list)


def test_next_closeout_calls_are_emitted_with_actionable_command() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rows = _next_closeout_calls(repo_root=repo_root, limit=5)
    assert rows
    first = rows[0]
    assert isinstance(first.get("next_call"), str)
    assert first["next_call"]
