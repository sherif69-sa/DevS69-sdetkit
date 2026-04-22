from __future__ import annotations

import json

from sdetkit import legacy_cli


def test_run_legacy_migrate_hint_single_json(capsys) -> None:
    rc = legacy_cli.run_legacy_migrate_hint(["--format", "json", "weekly-review-lane"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["mode"] == "single"
    assert payload["command"] == "weekly-review-lane"
    assert payload["preferred_surface"] == "python -m sdetkit weekly-review"


def test_run_legacy_migrate_hint_requires_command_or_all(capsys) -> None:
    rc = legacy_cli.run_legacy_migrate_hint([])
    assert rc == 2
    err = capsys.readouterr().err
    assert "expected command name" in err


def test_run_legacy_migrate_hint_all_json(capsys) -> None:
    rc = legacy_cli.run_legacy_migrate_hint(["--all", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "all"
    assert payload["count"] >= 1


def test_run_legacy_migrate_hint_rejects_command_with_all(capsys) -> None:
    rc = legacy_cli.run_legacy_migrate_hint(["--all", "weekly-review-lane"])
    assert rc == 2
    assert "either <command> or --all" in capsys.readouterr().err


def test_run_legacy_migrate_hint_text_mode(capsys) -> None:
    rc = legacy_cli.run_legacy_migrate_hint(["weekly-review-lane"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "python -m sdetkit weekly-review" in out


def test_emit_legacy_migration_hint_respects_toggle(monkeypatch, capsys) -> None:
    monkeypatch.setattr(legacy_cli, "legacy_hints_enabled", lambda: False)
    legacy_cli.emit_legacy_migration_hint("weekly-review-lane")
    assert capsys.readouterr().err == ""

    monkeypatch.setattr(legacy_cli, "legacy_hints_enabled", lambda: True)
    monkeypatch.setattr(legacy_cli, "legacy_migration_hint", lambda command: f"hint:{command}")
    legacy_cli.emit_legacy_migration_hint("weekly-review-lane")
    assert "hint:weekly-review-lane" in capsys.readouterr().err
