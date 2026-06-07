from __future__ import annotations

import importlib

from sdetkit.legacy_adapters import LEGACY_COMMAND_MODULES
from sdetkit.legacy_adapters.workflow_aliases import (
    CANONICAL_CLOSEOUT_COMMAND_MODULES,
    LEGACY_CLOSEOUT_COMMAND_MODULES,
    professional_canonical_command_for,
    professional_canonical_module_for,
)


def test_professional_canonical_closeout_commands_preserve_modules() -> None:
    legacy = "phase2-hardening-closeout"
    canonical = "release-readiness-hardening-completion-report"

    assert professional_canonical_command_for(legacy) == canonical
    assert professional_canonical_module_for("sdetkit.release_readiness_hardening") == (
        "sdetkit.release_readiness_hardening"
    )
    assert LEGACY_CLOSEOUT_COMMAND_MODULES[legacy] == "sdetkit.release_readiness_hardening"
    assert CANONICAL_CLOSEOUT_COMMAND_MODULES[canonical] == ("sdetkit.release_readiness_hardening")
    assert LEGACY_COMMAND_MODULES[legacy] == "sdetkit.release_readiness_hardening"
    assert LEGACY_COMMAND_MODULES[canonical] == "sdetkit.release_readiness_hardening"


def test_professional_canonical_command_aliases_are_registered() -> None:
    expected = {
        "acceleration-completion-report": "sdetkit.acceleration",
        "scale-completion-report": "sdetkit.scale",
        "release-prioritization-completion-report": "sdetkit.release_prioritization",
        "release-readiness-hardening-completion-report": ("sdetkit.release_readiness_hardening"),
        "release-readiness-wrap-handoff-completion-report": (
            "sdetkit.release_readiness_wrap_handoff"
        ),
        "platform-readiness-preplan-completion-report": ("sdetkit.platform_readiness_preplan"),
        "platform-readiness-kickoff-completion-report": ("sdetkit.platform_readiness_kickoff"),
        "platform-readiness-wrap-publication-completion-report": (
            "sdetkit.platform_readiness_wrap_publication"
        ),
    }

    for command, module in expected.items():
        assert CANONICAL_CLOSEOUT_COMMAND_MODULES[command] == module
        assert LEGACY_COMMAND_MODULES[command] == module


def test_professional_naming_aliases_preserve_private_workflow_templates() -> None:
    modules = [
        "sdetkit.release_readiness_kickoff",
        "sdetkit.release_readiness_hardening",
        "sdetkit.release_readiness_wrap_handoff",
        "sdetkit.platform_readiness_preplan",
        "sdetkit.platform_readiness_kickoff",
        "sdetkit.platform_readiness_wrap_publication",
    ]

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert hasattr(module, "_DEFAULT_PAGE_TEMPLATE")


def test_professional_naming_import_alias_modules_load() -> None:
    aliases = {
        "sdetkit.example": "sdetkit.example",
        "sdetkit.example_asset": "sdetkit.example_asset",
        "sdetkit.example_asset2": "sdetkit.example_asset2",
        "sdetkit.baseline_hardening": "sdetkit.baseline_hardening",
        "sdetkit.baseline_wrap": "sdetkit.baseline_wrap",
        "sdetkit.release_readiness_kickoff": "sdetkit.release_readiness_kickoff",
        "sdetkit.release_readiness_hardening": "sdetkit.release_readiness_hardening",
        "sdetkit.release_readiness_wrap_handoff": "sdetkit.release_readiness_wrap_handoff",
        "sdetkit.release_readiness_utilities": "sdetkit.release_readiness_utilities",
        "sdetkit.platform_readiness_preplan": "sdetkit.platform_readiness_preplan",
        "sdetkit.platform_readiness_kickoff": "sdetkit.platform_readiness_kickoff",
        "sdetkit.platform_readiness_wrap_publication": "sdetkit.platform_readiness_wrap_publication",
        "sdetkit.phases.release_readiness_kickoff": "sdetkit.phases.release_readiness_kickoff",
        "sdetkit.phases.release_readiness_hardening": "sdetkit.phases.release_readiness_hardening",
        "sdetkit.phases.release_readiness_wrap_handoff": (
            "sdetkit.phases.release_readiness_wrap_handoff"
        ),
        "sdetkit.phases.platform_readiness_preplan": "sdetkit.phases.platform_readiness_preplan",
        "sdetkit.phases.platform_readiness_kickoff": "sdetkit.phases.platform_readiness_kickoff",
        "sdetkit.phases.platform_readiness_wrap_publication": (
            "sdetkit.phases.platform_readiness_wrap_publication"
        ),
    }

    for canonical_module, legacy_module in aliases.items():
        imported = importlib.import_module(canonical_module)
        legacy = importlib.import_module(legacy_module)
        assert imported is not None
        assert legacy is not None
