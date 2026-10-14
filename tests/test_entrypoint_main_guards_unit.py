from __future__ import annotations

import runpy
import sys

import pytest

from sdetkit.checks.base import CheckDefinition, CheckProfile, RegistrySnapshot


def _run_module_isolated(module_name: str) -> None:
    sys.modules.pop(module_name, None)
    runpy.run_module(module_name, run_name="__main__")


def test_root_main_guard_executes_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sdetkit", "--version"])

    with pytest.raises(SystemExit) as excinfo:
        _run_module_isolated("sdetkit.__main__")
    assert excinfo.value.code == 0


def test_cli_main_guard_executes_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sdetkit", "--version"])

    with pytest.raises(SystemExit) as excinfo:
        _run_module_isolated("sdetkit.cli.__main__")
    assert excinfo.value.code == 0


def test_registry_snapshot_checks_for_profile() -> None:
    check = CheckDefinition(
        id="lint", title="Lint", category="lint", cost="cheap", truth_level="smoke"
    )
    profile = CheckProfile(
        name="quick",
        description="",
        default_truth_level="smoke",
        merge_truth=False,
        check_ids=("lint",),
    )
    snapshot = RegistrySnapshot(profiles={"quick": profile}, checks={"lint": check})

    checks = snapshot.checks_for_profile("quick")
    assert checks[0].id == "lint"
