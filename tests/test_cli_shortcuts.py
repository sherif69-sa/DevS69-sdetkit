from __future__ import annotations

from sdetkit import cli_shortcuts


def test_dispatch_preparse_shortcut_dispatches_known_module() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 7

    rc = cli_shortcuts.dispatch_preparse_shortcut(
        ["report", "--format", "json"],
        no_legacy_hint=False,
        run_module_main=_runner,
    )
    assert rc == 7
    assert calls == [("sdetkit.report", ["--format", "json"])]


def test_dispatch_preparse_shortcut_handles_dev_alias() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 3

    rc = cli_shortcuts.dispatch_preparse_shortcut(
        ["dev", "lint"],
        no_legacy_hint=False,
        run_module_main=_runner,
    )
    assert rc == 3
    assert calls == [("sdetkit.repo", ["dev", "lint"])]


def test_dispatch_preparse_shortcut_returns_none_for_unknown() -> None:
    rc = cli_shortcuts.dispatch_preparse_shortcut(
        ["unknown-cmd"],
        no_legacy_hint=False,
        run_module_main=lambda _module, _args: 0,
    )
    assert rc is None
