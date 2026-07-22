from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any

import pytest

WRAPPER_MODULES = (
    "sdetkit.continuous_upgrade_automation",
    "sdetkit.continuous_upgrade_baseline",
    "sdetkit.continuous_upgrade_contracts",
    "sdetkit.continuous_upgrade_docs",
    "sdetkit.continuous_upgrade_foundation",
    "sdetkit.continuous_upgrade_governance",
    "sdetkit.continuous_upgrade_operations",
    "sdetkit.continuous_upgrade_platform",
    "sdetkit.continuous_upgrade_quality",
    "sdetkit.continuous_upgrade_readiness",
    "sdetkit.continuous_upgrade_release",
)


@pytest.mark.parametrize("module_name", WRAPPER_MODULES)
def test_continuous_upgrade_wrapper_delegates_to_shared_lane(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
) -> None:
    module: ModuleType = import_module(module_name)
    observed: dict[str, Any] = {}

    def fake_run_lane(argv: list[str] | None, config: dict[str, object]) -> int:
        observed["argv"] = argv
        observed["config"] = config
        return 17

    monkeypatch.setattr(module, "run_lane", fake_run_lane)
    argv = ["--format", "json"]

    assert module.main(argv) == 17
    assert observed == {"argv": argv, "config": module._CFG}
    assert str(module._CFG["name"]).startswith("continuous-upgrade-")
