from __future__ import annotations

from sdetkit import release_dispatch


def test_dispatch_release_subcommand_gate() -> None:
    calls: list[tuple[str, list[str]]] = []

    def _runner(module: str, args) -> int:
        calls.append((module, list(args)))
        return 0

    rc = release_dispatch.dispatch_release_subcommand(
        ["gate", "--format", "json"],
        run_module_main=_runner,
    )
    assert rc == 0
    assert calls == [("sdetkit.gate", ["--format", "json"])]


def test_dispatch_release_subcommand_requires_subcommand(capsys) -> None:
    rc = release_dispatch.dispatch_release_subcommand([], run_module_main=lambda _m, _a: 0)
    assert rc == 2
    assert "expected subcommand" in capsys.readouterr().err


def test_dispatch_release_subcommand_rejects_unknown(capsys) -> None:
    rc = release_dispatch.dispatch_release_subcommand(
        ["unknown"],
        run_module_main=lambda _m, _a: 0,
    )
    assert rc == 2
    assert "supported subcommands" in capsys.readouterr().err
