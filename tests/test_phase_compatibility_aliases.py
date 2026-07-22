from __future__ import annotations

import importlib
import sys

import pytest

PHASE_ALIASES = (
    ("sdetkit.phases.phase1_hardening", "sdetkit.phases.baseline_hardening"),
    ("sdetkit.phases.phase1_wrap", "sdetkit.phases.baseline_wrap"),
    ("sdetkit.phases.phase2_hardening", "sdetkit.phases.release_readiness_hardening"),
    ("sdetkit.phases.phase2_kickoff", "sdetkit.phases.release_readiness_kickoff"),
    (
        "sdetkit.phases.phase2_wrap_handoff",
        "sdetkit.phases.release_readiness_wrap_handoff",
    ),
    ("sdetkit.phases.phase3_kickoff", "sdetkit.phases.platform_readiness_kickoff"),
    ("sdetkit.phases.phase3_preplan", "sdetkit.phases.platform_readiness_preplan"),
    (
        "sdetkit.phases.phase3_wrap_publication",
        "sdetkit.phases.platform_readiness_wrap_publication",
    ),
    ("sdetkit.phases.phase_boost", "sdetkit.phases.readiness_boost"),
)


@pytest.mark.parametrize(("legacy_name", "canonical_name"), PHASE_ALIASES)
def test_legacy_phase_module_resolves_to_canonical_module(
    legacy_name: str,
    canonical_name: str,
) -> None:
    canonical = importlib.import_module(canonical_name)
    sys.modules.pop(legacy_name, None)

    legacy = importlib.import_module(legacy_name)

    assert legacy is canonical
    assert sys.modules[legacy_name] is canonical
