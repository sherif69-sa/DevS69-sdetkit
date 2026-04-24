from __future__ import annotations

import json
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


def test_kpi_report_main_guard_executes_with_valid_args(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps(
            {
                "time_to_first_success_minutes": 12,
                "lint_debt_count": 3,
                "type_debt_count": 4,
                "ci_cycle_minutes": 8,
                "release_gate_pass_rate": 0.9,
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kpi_report",
            "--current",
            str(current),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        _run_module_isolated("sdetkit.kpi_report")
    assert excinfo.value.code == 0
    assert out_json.exists()
    assert out_md.exists()


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
