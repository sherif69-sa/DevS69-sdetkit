from __future__ import annotations

import json
from types import SimpleNamespace

from sdetkit import playbooks_cli


def test_playbooks_validate_recommended_json(capsys) -> None:
    rc = playbooks_cli.main(["validate", "--recommended", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["counts"]["failed"] == 0
    assert payload["counts"]["selected"] > 0
    names = [item["name"] for item in payload["results"]]
    assert names == sorted(names)


def test_playbooks_validate_unknown_name_fails(capsys) -> None:
    rc = playbooks_cli.main(["validate", "--name", "nope-nope-nope", "--format", "json"])
    io = capsys.readouterr()
    assert rc == 2
    assert io.out == ""
    assert io.err.strip() == "playbooks: unknown name"


def test_playbooks_validate_legacy_selection_only_has_legacy(capsys) -> None:
    rc = playbooks_cli.main(["validate", "--legacy", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert all(
        item["name"].startswith("day") or item["name"].endswith("-closeout")
        for item in payload["results"]
    )


def test_playbooks_validate_aliases_are_only_alias_names(capsys) -> None:
    rc = playbooks_cli.main(["validate", "--aliases", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["results"]
    assert all(not item["name"].startswith("day") for item in payload["results"])
    assert all(item["canonical"].startswith("day") for item in payload["results"])


def test_playbooks_validate_all_includes_multiple_groups(capsys) -> None:
    rc = playbooks_cli.main(["validate", "--all", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    names = [item["name"] for item in payload["results"]]
    assert "onboarding" in names
    assert any(name.startswith("day") for name in names)


def test_playbooks_validate_scan_handles_missing_main(monkeypatch, capsys) -> None:
    real_import_module = playbooks_cli.import_module

    def fake_import_module(name: str):
        if name == "sdetkit.onboarding":
            return SimpleNamespace()
        return real_import_module(name)

    monkeypatch.setattr(playbooks_cli, "import_module", fake_import_module)

    rc = playbooks_cli.main(["validate", "--name", "onboarding", "--format", "json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failed"] == ["onboarding"]
    assert payload["results"][0]["error"] == "missing callable main"


def test_playbooks_validate_scan_handles_import_error(monkeypatch, capsys) -> None:
    real_import_module = playbooks_cli.import_module

    def fake_import_module(name: str):
        if name == "sdetkit.onboarding":
            raise RuntimeError("boom")
        return real_import_module(name)

    monkeypatch.setattr(playbooks_cli, "import_module", fake_import_module)

    rc = playbooks_cli.main(["validate", "--name", "onboarding", "--format", "json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failed"] == ["onboarding"]
    assert payload["results"][0]["error"] == "boom"
