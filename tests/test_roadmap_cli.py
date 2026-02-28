from __future__ import annotations

from sdetkit import roadmap
from sdetkit.cli import main as cli_main


def test_roadmap_manifest_has_entries() -> None:
    entries = roadmap.load_manifest()
    assert len(entries) > 0


def test_roadmap_day69_plan_resolves_if_present() -> None:
    e = roadmap.get_entry(69)
    assert e is not None
    if e.plan_file is not None:
        assert e.plan_path is not None


def test_cli_roadmap_list_smoke(capsys) -> None:
    rc = cli_main(["roadmap", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() != ""
