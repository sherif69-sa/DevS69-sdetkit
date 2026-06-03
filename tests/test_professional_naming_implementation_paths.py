from __future__ import annotations

import importlib
from pathlib import Path


def test_legacy_phase_modules_remain_compatible_after_canonical_move() -> None:
    pairs = {
        "sdetkit.phase1_hardening": "sdetkit.baseline_hardening",
        "sdetkit.phase1_wrap": "sdetkit.baseline_wrap",
        "sdetkit.phase2_kickoff": "sdetkit.release_readiness_kickoff",
        "sdetkit.phase2_hardening": "sdetkit.release_readiness_hardening",
        "sdetkit.phase2_wrap_handoff": "sdetkit.release_readiness_wrap_handoff",
        "sdetkit.phase3_preplan": "sdetkit.platform_readiness_preplan",
        "sdetkit.phase3_kickoff": "sdetkit.platform_readiness_kickoff",
        "sdetkit.phase3_wrap_publication": "sdetkit.platform_readiness_wrap_publication",
    }

    for legacy_name, canonical_name in pairs.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert legacy is not None
        assert canonical is not None
        if hasattr(canonical, "_DEFAULT_PAGE_TEMPLATE"):
            assert legacy._DEFAULT_PAGE_TEMPLATE == canonical._DEFAULT_PAGE_TEMPLATE


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


def test_legacy_implementation_paths_are_wrappers_not_deleted() -> None:
    wrapper_paths = [
        Path("src/sdetkit/demo.py"),
        Path("src/sdetkit/demo_asset.py"),
        Path("src/sdetkit/demo_asset2.py"),
        Path("src/sdetkit/phases/phase1_hardening.py"),
        Path("src/sdetkit/phases/phase1_wrap.py"),
        Path("src/sdetkit/phases/phase2_kickoff.py"),
        Path("src/sdetkit/phases/phase2_hardening.py"),
        Path("src/sdetkit/phases/phase2_wrap_handoff.py"),
        Path("src/sdetkit/phases/phase3_preplan.py"),
        Path("src/sdetkit/phases/phase3_kickoff.py"),
        Path("src/sdetkit/phases/phase3_wrap_publication.py"),
        Path("src/sdetkit/agent/demo.py"),
    ]

    for path in wrapper_paths:
        text = path.read_text(encoding="utf-8")
        assert "_compat_alias" in text
