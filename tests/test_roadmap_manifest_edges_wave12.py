from __future__ import annotations

import json
from pathlib import Path

import pytest

import sdetkit.roadmap_manifest as rm


def _touch(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_script_lane_match_and_heading_helpers() -> None:
    assert rm._script_matches_closeout_lane(
        Path("check_release_readiness_closeout_contract.py"), "release_readiness"
    )
    assert not rm._script_matches_closeout_lane(Path("check_release_contract.py"), "")
    assert not rm._script_matches_closeout_lane(Path("check_ops_closeout.py"), "release_readiness")

    assert rm._first_heading("\n# Title\ntext") == "Title"
    assert rm._first_heading("plain\n##\n") is None


def test_repo_root_resolution_walks_up_and_falls_back_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    nested = repo / "a" / "b" / "c.py"
    _touch(repo / "pyproject.toml", "[project]\nname='x'\n")
    _touch(nested, "")

    assert rm._repo_root(nested) == repo

    outside = tmp_path / "outside" / "x.py"
    _touch(outside, "")
    monkeypatch.chdir(tmp_path)
    assert rm._repo_root(outside) == tmp_path


def test_closeout_inventory_uses_lane_matched_contract_candidates(tmp_path: Path) -> None:
    _touch(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    _touch(tmp_path / "src/sdetkit/release_readiness_closeout_21.py", '"""day21 marker"""\n')
    _touch(
        tmp_path / "tests/test_release_readiness_closeout.py",
        "from sdetkit import release_readiness_closeout_21\n",
    )
    # lane-match fallback candidate (no id in filename)
    _touch(tmp_path / "scripts/check_release_readiness_closeout_contract.py", "print('ok')\n")

    inv = rm._closeout_inventory(tmp_path)
    assert inv["count"] == 1
    assert inv["fully_aligned_count"] == 1
    assert inv["entries"][0]["contract_scripts"] == 1
    assert inv["entries"][0]["tests_referencing_module"] == 1


def test_next_closeout_calls_handles_non_list_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rm, "_closeout_inventory", lambda _root: {"entries": "bad"})
    assert rm._next_closeout_calls(limit=2) == []


def test_next_closeout_calls_fallback_when_inventory_rows_are_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rm,
        "_closeout_inventory",
        lambda _root: {
            "entries": [
                {
                    "id": 1,
                    "lane": "a",
                    "module": "sdetkit.alpha",
                    "tests_referencing_module": 1,
                    "contract_scripts": 1,
                    "legacy_anchor_refs_in_module": 0,
                    "contract_script_paths": ["scripts/check_a_1.py"],
                }
            ]
        },
    )
    rows = rm._next_closeout_calls(limit=1)
    assert rows and rows[0]["next_call"].startswith("pytest -q -k")


def test_build_manifest_reads_plan_title_name_and_detects_duplicates(tmp_path: Path) -> None:
    _touch(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    _touch(tmp_path / "docs/roadmap/reports/impact-7-sprint-report.md", "# Impact 7\n")
    _touch(tmp_path / "docs/roadmap/phase3/plans/day7.json", json.dumps({"name": "Plan Seven"}))

    manifest = rm.build_manifest(repo_root=tmp_path)
    assert manifest["phases"][0]["report_title"] == "Impact 7"
    assert manifest["phases"][0]["plan_title"] == "Plan Seven"

    _touch(tmp_path / "docs/roadmap/reports/impact-7-another-report.md", "# Dup\n")
    with pytest.raises(ValueError, match="duplicate report"):
        rm.build_manifest(repo_root=tmp_path)


def test_build_manifest_detects_duplicate_plan(tmp_path: Path) -> None:
    _touch(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    _touch(tmp_path / "docs/roadmap/reports/impact-8-sprint-report.md", "# Impact 8\n")
    _touch(tmp_path / "docs/roadmap/phase3/plans/day8.json", "{}")
    _touch(tmp_path / "docs/roadmap/phase3/plans/impact8-extra.json", "{}")

    with pytest.raises(ValueError, match="duplicate plan"):
        rm.build_manifest(repo_root=tmp_path)


def test_main_covering_help_unknown_print_write_check_closeout_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _touch(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    _touch(tmp_path / "docs/roadmap/reports/impact-1-sprint-report.md", "# R1\n")
    _touch(tmp_path / "docs/roadmap/phase3/plans/day1.json", json.dumps({"title": "P1"}))

    monkeypatch.chdir(tmp_path)

    assert rm.main(["--help"]) == 0
    assert "usage:" in capsys.readouterr().out

    assert rm.main(["unknown"]) == 2
    assert "unknown command" in capsys.readouterr().err

    assert rm.main(["print"]) == 0
    printed = capsys.readouterr().out
    assert '"phases"' in printed

    assert rm.main(["write"]) == 0
    write_out = capsys.readouterr().out.strip()
    assert write_out.endswith("docs/roadmap/manifest.json")

    assert rm.main(["check"]) == 0
    capsys.readouterr()

    # force stale branch
    monkeypatch.setattr(rm, "check_manifest", lambda repo_root=None: False)
    assert rm.main(["check"]) == 1
    assert "stale" in capsys.readouterr().err

    assert rm.main(["closeout-next", "bad"]) == 2
    assert "invalid limit" in capsys.readouterr().err

    assert rm.main(["closeout-next", "2"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"count", "next_calls"}
