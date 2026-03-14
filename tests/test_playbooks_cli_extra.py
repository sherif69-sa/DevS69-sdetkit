from __future__ import annotations

import argparse
import types
from pathlib import Path

from sdetkit import playbooks_cli as pc


def test_alias_helpers_and_discovery(tmp_path: Path) -> None:
    (tmp_path / "day77_community_touchpoint_closeout.py").write_text("x", encoding="utf-8")
    (tmp_path / "day99_custom.py").write_text("x", encoding="utf-8")
    (tmp_path / "not_legacy.py").write_text("x", encoding="utf-8")

    mods = pc._discover_legacy_modules(tmp_path)
    assert "day77_community_touchpoint_closeout" in mods
    assert (
        pc._alias_for_series_closeout("day77_community_touchpoint_closeout")
        == "community-touchpoint-closeout"
    )
    assert pc._alias_for_series_module("day99_custom") == "custom"


def test_search_filters_day_tokens() -> None:
    assert pc._apply_search_list(["day-review", "weekly-review"], None) == ["weekly-review"]
    assert pc._apply_search_list(["weekly-review", "release"], "day weekly") == ["weekly-review"]
    assert pc._apply_search_aliases({"day-alias": "weekly-review", "stable": "release"}, None) == {
        "stable": "release"
    }


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


def test_cmd_run_success_and_validate_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(pc, "_pkg_dir", lambda: Path("/tmp/none"))
    monkeypatch.setattr(
        pc,
        "_build_registry",
        lambda pkg: ({"alias": "demo_mod", "broken": "broken_mod"}, {"alias": "demo"}),
    )

    good_mod = types.SimpleNamespace(main=lambda argv: 7)
    broken_mod = types.SimpleNamespace(main="not-callable")

    def _fake_import(name: str):
        if name == "sdetkit.demo_mod":
            return good_mod
        if name == "sdetkit.broken_mod":
            return broken_mod
        raise RuntimeError("boom")

    monkeypatch.setattr(pc, "import_module", _fake_import)

    run_ns = argparse.Namespace(name="alias", args=["--", "--flag"])
    assert pc._cmd_run(run_ns) == 7

    json_ns = argparse.Namespace(
        all=False,
        recommended=False,
        legacy=False,
        aliases=False,
        name=["alias", "broken"],
        format="json",
    )
    assert pc._cmd_validate(json_ns) == 2
    out = capsys.readouterr().out
    assert '"failed": [' in out
    assert '"canonical": "demo"' in out
