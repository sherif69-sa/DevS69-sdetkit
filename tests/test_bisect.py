"""Tests for sdetkit bisect: automated flake bisection and git blame attribution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import flake_hunter

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_git_commits_and_info() -> None:
    commits = flake_hunter._git_commits(REPO_ROOT, good_ref=None, bad_ref="HEAD", max_commits=3)
    assert len(commits) <= 3
    if commits:
        info = flake_hunter._git_commit_info(REPO_ROOT, commits[-1])
        assert "commit" in info
        assert "author" in info
        assert "message" in info
        assert isinstance(info["changed_files"], list)


def test_bisect_flaky_test_clean_suite(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_always_passes(): assert True\n", encoding="utf-8")

    report = flake_hunter.bisect_flaky_test(
        tmp_path,
        str(test_file),
        runs=2,
        max_commits=3,
    )
    assert report["schema_version"] == "sdetkit.bisect.v1"
    assert report["verdict"] in ("NOT_REPRODUCED", "ATTRIBUTED")
    assert "culprit_commit" in report
    assert "recommendation" in report


def test_render_bisect_markdown() -> None:
    fake_report = {
        "schema_version": "sdetkit.bisect.v1",
        "target": "tests/test_demo.py::test_race",
        "verdict": "ATTRIBUTED",
        "attribution_type": "DIRECT_TEST_MODIFICATION",
        "culprit_commit": {
            "commit": "a1b2c3d4",
            "full_sha": "a1b2c3d4e5f60000000000000000000000000000",
            "author": "Alice Developer <alice@example.test>",
            "date": "2026-11-20 01:00:00 +0000",
            "message": "feat: update test assertions",
            "is_direct_test_edit": True,
        },
        "history": [
            {
                "commit": "00112233",
                "verdict": "clean",
                "flake_rate": 0.0,
                "passed_count": 3,
                "failed_count": 0,
            },
            {
                "commit": "a1b2c3d4",
                "verdict": "flaky",
                "flake_rate": 33.3,
                "passed_count": 2,
                "failed_count": 1,
            },
        ],
        "recommendation": "Commit a1b2c3d4 introduced flakiness into tests/test_demo.py::test_race.",
    }

    md = flake_hunter.render_bisect_markdown(fake_report)
    assert "# SDETKit Flake Bisection & Git Blame Attribution" in md
    assert "**Verdict:** `ATTRIBUTED`" in md
    assert "Alice Developer" in md
    assert "Direct test file edit" in md
    assert "Bisection Progression History" in md
    assert "a1b2c3d4" in md


def test_bisect_main_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    test_file = tmp_path / "test_example.py"
    test_file.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")

    out_json = tmp_path / "bisect.json"
    rc = flake_hunter.bisect_main(
        [
            str(test_file),
            "--repo-root",
            str(tmp_path),
            "--runs",
            "2",
            "--format",
            "json",
            "--out",
            str(out_json),
        ]
    )
    assert rc in (0, 1)
    captured = capsys.readouterr()
    assert out_json.is_file()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == "sdetkit.bisect.v1"
    assert json.loads(captured.out)["schema_version"] == "sdetkit.bisect.v1"

    # Text format
    rc_text = flake_hunter.bisect_main(
        [str(test_file), "--repo-root", str(tmp_path), "--runs", "1", "--format", "text"]
    )
    assert rc_text in (0, 1)
    captured_text = capsys.readouterr()
    assert "verdict=" in captured_text.out


def test_flake_hunter_main_routes_to_bisect(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = tmp_path / "test_route.py"
    test_file.write_text("def test_route(): pass\n", encoding="utf-8")

    rc = flake_hunter.main(
        ["bisect", str(test_file), "--repo-root", str(tmp_path), "--runs", "1", "--format", "json"]
    )
    assert rc in (0, 1)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "sdetkit.bisect.v1"
