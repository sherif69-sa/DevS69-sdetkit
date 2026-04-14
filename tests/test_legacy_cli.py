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
