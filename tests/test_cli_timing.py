from __future__ import annotations

from sdetkit import cli_timing


def test_cli_timing_enabled_when_env_true(monkeypatch) -> None:
    monkeypatch.setenv("SDETKIT_CLI_TIMING", "true")
    assert cli_timing.cli_timing_enabled() is True


def test_cli_timing_enabled_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("SDETKIT_CLI_TIMING", raising=False)
    assert cli_timing.cli_timing_enabled() is False


def test_emit_cli_timing_writes_to_stderr(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_CLI_TIMING", "1")
    cli_timing.emit_cli_timing("event=test")
    captured = capsys.readouterr()
    assert "[sdetkit.cli.timing] event=test" in captured.err


def test_loaded_module_count_reports_positive_value() -> None:
    assert cli_timing.loaded_module_count() > 0


def test_emit_cli_startup_snapshot_writes_module_count(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SDETKIT_CLI_TIMING", "1")
    cli_timing.emit_cli_startup_snapshot("gate")
    captured = capsys.readouterr()
    assert "event=startup command=gate modules_loaded=" in captured.err
