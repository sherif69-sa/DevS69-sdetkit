from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sdetkit.feature_registry import (
    ensure_feature_registry_docs_synced,
    load_feature_registry,
    render_feature_registry_docs_block,
    validate_feature_registry_contract,
)
from sdetkit.public_surface_contract import PUBLIC_SURFACE_CONTRACT


def test_feature_registry_entries_are_loadable() -> None:
    rows = load_feature_registry()

    assert rows
    assert all(row.tier in {"A", "B", "C"} for row in rows)
    assert all(row.status in {"stable", "advanced", "experimental"} for row in rows)
    assert all(row.example.startswith("python -m sdetkit") for row in rows)


def test_feature_registry_contract_links_existing_assets() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    errors = validate_feature_registry_contract(repo_root)

    assert errors == []


def test_feature_registry_docs_table_is_synced() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    errors = ensure_feature_registry_docs_synced(repo_root)

    assert errors == []


def test_feature_registry_commands_are_in_public_surface_contract() -> None:
    known: set[str] = set()
    for family in PUBLIC_SURFACE_CONTRACT:
        known.update(family.top_level_commands)

    rows = load_feature_registry()
    assert all(row.command in known for row in rows)


def test_feature_registry_docs_block_uses_docs_relative_links() -> None:
    rows = load_feature_registry()
    block = render_feature_registry_docs_block(rows)
    row_lines = [line for line in block.splitlines() if line.startswith("| `")]

    assert "(../tests/" in block
    assert "(docs/" not in block
    assert "(doctor.md)" in block or "(cli.md)" in block
    assert len(row_lines) == len(rows)


def test_contract_script_runs_without_external_pythonpath() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [sys.executable, "scripts/check_feature_registry_contract.py", "--repo-root", str(repo_root)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "feature-registry-contract check passed" in proc.stdout


def test_sync_script_check_mode_runs_without_external_pythonpath() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [sys.executable, "scripts/sync_feature_registry_docs.py", "--repo-root", str(repo_root), "--check"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "feature-registry docs table is up to date" in proc.stdout
