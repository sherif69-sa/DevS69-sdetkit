from __future__ import annotations

import importlib
import sys


def test_cli_import_does_not_eager_load_modules() -> None:
    modules = [
        "sdetkit.cli",
        "sdetkit.expansion_automation_41",
        "sdetkit.optimization_foundation",
        "sdetkit.acceleration",
        "sdetkit.scale",
        "sdetkit.expansion",
        "sdetkit.optimization",
        "sdetkit.reliability",
        "sdetkit.objection_handling",
        "sdetkit.weekly_review",
        "sdetkit.execution_prioritization",
    ]
    saved: dict[str, object] = {}
    for name in modules:
        existing = sys.modules.pop(name, None)
        if existing is not None:
            saved[name] = existing
    try:
        importlib.import_module("sdetkit.cli")
        for name in modules[1:]:
            assert name not in sys.modules
    finally:
        for name in modules:
            sys.modules.pop(name, None)
        sys.modules.update(saved)
