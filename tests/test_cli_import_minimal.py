from __future__ import annotations

import importlib
import sys


def test_cli_import_does_not_eager_load_closeout_modules() -> None:
    modules = [
        "sdetkit.cli",
        "sdetkit.expansion_automation_41",
        "sdetkit.optimization_closeout_42",
        "sdetkit.acceleration_closeout_43",
        "sdetkit.scale_closeout_44",
        "sdetkit.expansion_closeout_45",
        "sdetkit.optimization_closeout_46",
        "sdetkit.reliability_closeout_47",
        "sdetkit.objection_closeout_48",
        "sdetkit.weekly_review_closeout_49",
        "sdetkit.execution_prioritization_closeout_50",
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
