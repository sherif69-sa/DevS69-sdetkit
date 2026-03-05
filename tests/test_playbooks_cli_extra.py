from __future__ import annotations

import argparse
from pathlib import Path

from sdetkit import playbooks_cli as pc


def test_alias_helpers_and_discovery(tmp_path: Path) -> None:
    (tmp_path / "day77_community_touchpoint_closeout.py").write_text("x", encoding="utf-8")
    (tmp_path / "day99_custom.py").write_text("x", encoding="utf-8")
    (tmp_path / "not_legacy.py").write_text("x", encoding="utf-8")

    mods = pc._discover_legacy_modules(tmp_path)
    assert "day77_community_touchpoint_closeout" in mods
    assert (
        pc._alias_for_day_closeout("day77_community_touchpoint_closeout")
        == "community-touchpoint-closeout"
    )
    assert pc._alias_for_day_module("day99_custom") == "custom"


def test_cmd_run_unknown_and_validate_unknown(monkeypatch, capsys) -> None:
    monkeypatch.setattr(pc, "_pkg_dir", lambda: Path("/tmp/none"))
    monkeypatch.setattr(pc, "_build_registry", lambda pkg: ({"a": "mod_a"}, {}))

    ns = argparse.Namespace(name="missing", args=[])
    assert pc._cmd_run(ns) == 2
    assert "unknown name" in capsys.readouterr().err

    ns2 = argparse.Namespace(
        all=False, recommended=False, legacy=False, aliases=False, name=["zzz"], format="text"
    )
    assert pc._cmd_validate(ns2) == 2


def test_main_default_list_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        pc,
        "_list_payload",
        lambda **kwargs: {
            "recommended": [],
            "legacy": [],
            "aliases": {},
            "playbooks": [],
            "counts": {},
        },
    )
    assert pc.main(["list", "--format", "json"]) == 0
    assert "recommended" in capsys.readouterr().out
