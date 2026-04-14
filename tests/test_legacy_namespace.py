from __future__ import annotations

from sdetkit import legacy_namespace


def test_handle_legacy_namespace_returns_none_for_non_legacy() -> None:
    assert legacy_namespace.handle_legacy_namespace(["gate", "fast"]) is None


def test_handle_legacy_namespace_lists_commands(capsys) -> None:
    rc = legacy_namespace.handle_legacy_namespace(["legacy", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "weekly-review-lane" in out


def test_handle_legacy_namespace_requires_subcommand(capsys) -> None:
    rc = legacy_namespace.handle_legacy_namespace(["legacy"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "expected a legacy command name" in err
