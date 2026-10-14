from __future__ import annotations

import importlib


def test_canonical_phase_package_modules_own_templates() -> None:
    canonical_modules = [
        "sdetkit.phases.baseline_hardening",
        "sdetkit.phases.baseline_wrap",
        "sdetkit.phases.release_readiness_kickoff",
        "sdetkit.phases.release_readiness_hardening",
        "sdetkit.phases.release_readiness_wrap_handoff",
        "sdetkit.phases.platform_readiness_preplan",
        "sdetkit.phases.platform_readiness_kickoff",
        "sdetkit.phases.platform_readiness_wrap_publication",
    ]

    for module_name in canonical_modules:
        module = importlib.import_module(module_name)
        assert hasattr(module, "_DEFAULT_PAGE_TEMPLATE")
