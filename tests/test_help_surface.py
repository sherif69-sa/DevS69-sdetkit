from __future__ import annotations

from sdetkit.help_surface import is_hidden_command


def test_is_hidden_command_keeps_primary_namespaces_visible() -> None:
    assert is_hidden_command("playbooks") is False
    assert is_hidden_command("legacy") is False


def test_is_hidden_command_hides_legacy_and_closeout_namespaces() -> None:
    assert is_hidden_command("weekly-review-lane") is True
    assert is_hidden_command("scale-closeout") is True
