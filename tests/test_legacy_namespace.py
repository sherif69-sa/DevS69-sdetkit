from __future__ import annotations

from sdetkit import cli, legacy_namespace


def test_handle_legacy_namespace_returns_none_for_non_legacy() -> None:
    assert legacy_namespace.handle_legacy_namespace(["gate", "fast"]) is None


def test_handle_legacy_namespace_lists_commands(capsys) -> None:
    rc = legacy_namespace.handle_legacy_namespace(["legacy", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "weekly-review-lane" in out


def test_handle_legacy_namespace_noargs_shows_help(capsys) -> None:
    rc = legacy_namespace.handle_legacy_namespace(["legacy"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: sdetkit legacy" in out
    assert "migrate-hint" in out


def test_handle_legacy_namespace_routes_migrate_hint(monkeypatch) -> None:
    monkeypatch.setattr(legacy_namespace, "run_legacy_migrate_hint", lambda argv: 7)
    assert legacy_namespace.handle_legacy_namespace(["legacy", "migrate-hint", "x"]) == 7


def test_handle_legacy_namespace_unknown_subcommand_errors(capsys) -> None:
    rc = legacy_namespace.handle_legacy_namespace(["legacy", "unknown-subcmd"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "legacy error: unknown subcommand 'unknown-subcmd'" in err


def test_handle_legacy_namespace_known_legacy_command_passthrough() -> None:
    assert (
        legacy_namespace.handle_legacy_namespace(["legacy", "weekly-review-lane", "--help"]) is None
    )


def test_cli_main_unknown_legacy_subcommand_fails_fast(capsys) -> None:
    rc = cli.main(["legacy", "unknown-subcmd"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "legacy error: unknown subcommand 'unknown-subcmd'" in err


def test_handle_legacy_namespace_help_shows_help(capsys) -> None:
    rc = legacy_namespace.handle_legacy_namespace(["legacy", "--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: sdetkit legacy" in out
    assert "list" in out


def test_cli_main_legacy_help_without_show_hidden(capsys) -> None:
    rc = cli.main(["legacy", "--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: sdetkit legacy" in out


def test_cli_main_show_hidden_legacy_noargs_shows_help(capsys) -> None:
    rc = cli.main(["--show-hidden", "legacy"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: sdetkit legacy" in out


def test_cli_main_show_hidden_legacy_help_shows_help(capsys) -> None:
    rc = cli.main(["--show-hidden", "legacy", "--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage: sdetkit legacy" in out
