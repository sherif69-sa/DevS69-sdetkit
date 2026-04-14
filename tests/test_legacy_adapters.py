from __future__ import annotations

from sdetkit.legacy_adapters import LEGACY_COMMAND_MODULES, LEGACY_NAMESPACE_COMMANDS
from sdetkit.legacy_adapters.closeout import LEGACY_CLOSEOUT_COMMAND_MODULES
from sdetkit.legacy_adapters.continuous_upgrade import LEGACY_CONTINUOUS_UPGRADE_COMMAND_MODULES
from sdetkit.legacy_adapters.foundation import LEGACY_FOUNDATION_COMMAND_MODULES


def test_legacy_adapter_aggregation_preserves_all_mappings() -> None:
    expected = {
        **LEGACY_FOUNDATION_COMMAND_MODULES,
        **LEGACY_CLOSEOUT_COMMAND_MODULES,
        **LEGACY_CONTINUOUS_UPGRADE_COMMAND_MODULES,
    }
    assert LEGACY_COMMAND_MODULES == expected


def test_legacy_namespace_commands_live_in_foundation_adapter() -> None:
    for command in LEGACY_NAMESPACE_COMMANDS:
        assert command in LEGACY_FOUNDATION_COMMAND_MODULES
