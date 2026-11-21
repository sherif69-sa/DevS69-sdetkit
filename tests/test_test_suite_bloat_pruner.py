"""Tests for Frontier 22: Test Suite Bloat & Dead Code Pruner (sdetkit prune)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import dependency_map, safety_gate


def _setup_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    tests_d = repo / "tests"
    tests_d.mkdir(parents=True)

    # conftest.py with an autouse fixture and an unused zombie fixture
    (tests_d / "conftest.py").write_text(
        "import pytest\n\n"
        "@pytest.fixture(autouse=True)\n"
        "def auto_env():\n"
        "    return 'ready'\n\n"
        "@pytest.fixture\n"
        "def zombie_conftest_fix():\n"
        "    return 'never_used'\n",
        encoding="utf-8",
    )

    # test_suite_a.py
    (tests_d / "test_suite_a.py").write_text(
        "import pytest\n"
        "from unittest.mock import MagicMock\n\n"
        "@pytest.fixture\n"
        "def used_local_fix():\n"
        "    return 42\n\n"
        "def test_passing_with_assert(used_local_fix):\n"
        "    assert used_local_fix == 42\n\n"
        "def test_with_mock_and_context():\n"
        "    m = MagicMock()\n"
        "    m.call_me()\n"
        "    m.assert_called_once()\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError('boom')\n\n"
        "def test_empty_zero_assert():\n"
        "    x = 10\n"
        "    y = 20\n\n"
        "@pytest.mark.skip(reason='intentionally skipped')\n"
        "def test_skipped_no_assert():\n"
        "    pass\n",
        encoding="utf-8",
    )

    # test_suite_b.py (contains class and redundant tests)
    (tests_d / "test_suite_b.py").write_text(
        "class TestClassSuite:\n"
        "    def test_method_good(self):\n"
        "        assert True\n\n"
        "    def test_method_zero_assert(self):\n"
        "        msg = 'doing nothing'\n\n"
        "def helper_func(val):\n"
        "    return val * 2\n\n"
        "def test_redundant_one():\n"
        "    assert helper_func(2) == 4\n\n"
        "def test_redundant_two():\n"
        "    assert helper_func(3) == 6\n",
        encoding="utf-8",
    )

    # Simulated test durations for sloth test detection
    dot_sdetkit = repo / ".sdetkit"
    dot_sdetkit.mkdir(parents=True)
    durations = {
        "tests/test_suite_a.py::test_passing_with_assert": 2.50,
        "tests/test_suite_a.py::test_with_mock_and_context": 0.05,
    }
    (dot_sdetkit / "shard_durations.json").write_text(json.dumps(durations), encoding="utf-8")

    return repo


def test_audit_test_suite_bloat_detection(tmp_path: Path) -> None:
    repo = _setup_test_repo(tmp_path)
    report = dependency_map.audit_test_suite_bloat(repo, min_duration=1.0)

    assert report["schema_version"] == "sdetkit.test_bloat_audit.v1"
    assert report["total_test_files"] == 3  # conftest.py, test_suite_a.py, test_suite_b.py
    assert report["total_tests_audited"] >= 6

    # Verify zero-assertion tests detected
    zero_names = [z["test_name"] for z in report["zero_assertion_tests"]]
    assert "test_empty_zero_assert" in zero_names
    assert "TestClassSuite::test_method_zero_assert" in zero_names
    assert "test_skipped_no_assert" not in zero_names

    # Verify zombie fixtures detected
    zombie_names = [z["fixture_name"] for z in report["zombie_fixtures"]]
    assert "zombie_conftest_fix" in zombie_names
    assert "auto_env" not in zombie_names
    assert "used_local_fix" not in zombie_names

    # Verify sloth tests detected
    sloth_names = [s["test_name"] for s in report["sloth_tests"]]
    assert "test_passing_with_assert" in sloth_names

    # Verify redundant candidates detected
    assert len(report["redundant_candidates"]) >= 1

    # Verify bloat score and savings
    assert report["bloat_score"] > 0.0
    assert report["verdict"] in ("WARN", "BLOATED")
    assert report["estimated_ci_seconds_saved"] > 0.0
    assert len(report["pruning_prescriptions"]) >= 4


def test_prune_render_ascii_purity(tmp_path: Path) -> None:
    repo = _setup_test_repo(tmp_path)
    report = dependency_map.audit_test_suite_bloat(repo)

    md = dependency_map.render_prune_markdown(report)
    txt = dependency_map.render_prune_text(report)

    # Pure ASCII assertion
    assert all(ord(c) < 128 for c in md)
    assert all(ord(c) < 128 for c in txt)
    assert "# SDETKit Test Suite Bloat & Dead Code Audit" in md
    assert "SDETKit Prune: verdict=" in txt


def test_prune_cli_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _setup_test_repo(tmp_path)

    # 1. JSON format
    rc = dependency_map.prune_main(["--repo-root", str(repo), "--format", "json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "sdetkit.test_bloat_audit.v1"
    assert payload["bloat_score"] > 0.0

    # 2. Strict mode failure
    rc_strict = dependency_map.prune_main(["--repo-root", str(repo), "--strict"])
    capsys.readouterr()
    assert rc_strict == 1

    # 3. Max bloat failure
    rc_bloat = dependency_map.prune_main(["--repo-root", str(repo), "--max-bloat", "5.0"])
    capsys.readouterr()
    assert rc_bloat == 1

    # 4. Out file writing
    out_file = tmp_path / "bloat_out.json"
    rc_out = dependency_map.prune_main(["--repo-root", str(repo), "--out", str(out_file)])
    capsys.readouterr()
    assert rc_out == 0
    assert out_file.is_file()
    out_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert out_data["schema_version"] == "sdetkit.test_bloat_audit.v1"


def test_clean_suite_reports_clean(tmp_path: Path) -> None:
    repo = tmp_path / "clean_repo"
    tests_d = repo / "tests"
    tests_d.mkdir(parents=True)
    (tests_d / "test_clean.py").write_text(
        "def test_perfect_one():\n"
        "    assert 1 == 1\n\n"
        "def test_perfect_two():\n"
        "    assert 2 == 2\n",
        encoding="utf-8",
    )
    report = dependency_map.audit_test_suite_bloat(repo)
    assert report["bloat_score"] == 0.0
    assert report["verdict"] == "CLEAN"
    assert len(report["zero_assertion_tests"]) == 0
    assert len(report["zombie_fixtures"]) == 0
    assert len(report["sloth_tests"]) == 0
    assert report["ok"] is True


def test_ship_gate_with_max_bloat(tmp_path: Path) -> None:
    repo = _setup_test_repo(tmp_path)
    # With a high threshold, ship gate continues normally
    report_pass = safety_gate.evaluate_ship_gate(
        repo_root=repo,
        tier="1",
        max_bloat=100.0,
    )
    assert "test_suite_bloat" in [c["name"] for c in report_pass["checks"]]
