from __future__ import annotations

from types import SimpleNamespace

from sdetkit import cli


def test_run_module_main_silent_by_default(monkeypatch, capsys) -> None:
    monkeypatch.delenv("SDETKIT_CLI_TIMING", raising=False)
    monkeypatch.setattr(cli, "import_module", lambda _name: SimpleNamespace(main=lambda _a: 0))

    rc = cli._run_module_main("sdetkit.fake", ["--x"])

    assert rc == 0
    assert capsys.readouterr().err == ""


def test_run_module_main_emits_timing_when_enabled(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_CLI_TIMING", "1")
    monkeypatch.setattr(cli, "import_module", lambda _name: SimpleNamespace(main=lambda _a: 0))

    rc = cli._run_module_main("sdetkit.fake", ["--x", "--y"])

    assert rc == 0
    err = capsys.readouterr().err
    assert "[sdetkit.cli.timing]" in err
    assert "event=dispatch" in err
    assert "module=sdetkit.fake" in err


def test_build_root_parser_emits_timing_when_enabled(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_CLI_TIMING", "yes")

    cli._build_root_parser(show_hidden_commands=False)

    err = capsys.readouterr().err
    assert "[sdetkit.cli.timing]" in err
    assert "event=parser-build" in err
