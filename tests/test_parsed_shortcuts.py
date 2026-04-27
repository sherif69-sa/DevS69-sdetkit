from __future__ import annotations

from sdetkit import parsed_shortcuts


def test_dispatch_parsed_shortcut_known_command() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 5

    rc = parsed_shortcuts.dispatch_parsed_shortcut(
        "report",
        ["--format", "json"],
        run_module_main=_runner,
    )
    assert rc == 5
    assert calls == [("sdetkit.report", ["--format", "json"])]


def test_dispatch_parsed_shortcut_dev_alias() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 6

    rc = parsed_shortcuts.dispatch_parsed_shortcut(
        "dev",
        ["type"],
        run_module_main=_runner,
    )
    assert rc == 6
    assert calls == [("sdetkit.repo", ["dev", "type"])]


def test_dispatch_parsed_shortcut_unknown_command() -> None:
    rc = parsed_shortcuts.dispatch_parsed_shortcut(
        "unknown",
        [],
        run_module_main=lambda _module, _args: 0,
    )
    assert rc is None


def test_dispatch_parsed_shortcut_author_command() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 9

    rc = parsed_shortcuts.dispatch_parsed_shortcut(
        "author",
        ["--help"],
        run_module_main=_runner,
    )
    assert rc == 9
    assert calls == [("sdetkit.author_problem", ["--help"])]


def test_dispatch_parsed_shortcut_integration_command() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 4

    rc = parsed_shortcuts.dispatch_parsed_shortcut(
        "integration",
        ["topology-check"],
        run_module_main=_runner,
    )
    assert rc == 4
    assert calls == [("sdetkit.integration", ["topology-check"])]


def test_dispatch_parsed_shortcut_start_alias() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 3

    rc = parsed_shortcuts.dispatch_parsed_shortcut(
        "start",
        ["--journey", "fast-start", "--format", "markdown"],
        run_module_main=_runner,
    )
    assert rc == 3
    assert calls == [("sdetkit.onboarding", ["--journey", "fast-start", "--format", "markdown"])]
