from __future__ import annotations

import json

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
