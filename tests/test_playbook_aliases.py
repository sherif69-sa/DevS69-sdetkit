from __future__ import annotations

from types import SimpleNamespace

from sdetkit import playbook_aliases


def test_resolve_non_day_playbook_alias_fallback_on_import_error(monkeypatch) -> None:
    def _boom(_name: str):
        raise RuntimeError("no module")

    monkeypatch.setattr(playbook_aliases, "import_module", _boom)
    assert playbook_aliases.resolve_non_day_playbook_alias("phase1-wrap") == "phase1-wrap"


def test_resolve_non_day_playbook_alias_resolves_known_alias(monkeypatch) -> None:
    fake = SimpleNamespace(
        _pkg_dir=lambda: "unused",
        _build_registry=lambda _pkg: (
            {"phase1-wrap": "sdetkit.phase1_wrap_30"},
            {"phase1-wrap": "phase2-kickoff"},
        ),
    )
    monkeypatch.setattr(playbook_aliases, "import_module", lambda _name: fake)
    assert playbook_aliases.resolve_non_day_playbook_alias("phase1-wrap") == "phase2-kickoff"


def test_resolve_non_day_playbook_alias_keeps_impact_commands(monkeypatch) -> None:
    fake = SimpleNamespace(
        _pkg_dir=lambda: "unused",
        _build_registry=lambda _pkg: (
            {"impact12": "sdetkit.some"},
            {"impact12": "canonical-impact12"},
        ),
    )
    monkeypatch.setattr(playbook_aliases, "import_module", lambda _name: fake)
    assert playbook_aliases.resolve_non_day_playbook_alias("impact12") == "impact12"
