from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import change_verifier, flake_hunter


def test_create_and_run_replay_capsule(tmp_path: Path) -> None:
    test_dir = tmp_path / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_sample.py"
    test_file.write_text(
        "import os\n"
        "def test_failing_case():\n"
        "    if os.environ.get('FORCE_FAIL') == '1':\n"
        "        assert False, 'induced failure'\n"
        "    assert True\n",
        encoding="utf-8",
    )

    capsule_path = flake_hunter.create_replay_capsule(
        root=tmp_path,
        node_id=str(test_file) + "::test_failing_case",
        prng_seed=12345,
        chaos_profile={"socket_latency_us": 1000},
        env_overrides={"FORCE_FAIL": "1"},
        capsule_id="cap_repro_test",
    )
    assert capsule_path.is_file()
    data = json.loads(capsule_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["prng_seed"] == 12345
    assert data["env_overrides"]["FORCE_FAIL"] == "1"
    assert "replay_cmd" in data

    report = flake_hunter.replay_capsule(capsule_path, root=tmp_path)
    assert report["schema_version"] == "1.0"
    assert report["verdict"] == "REPRODUCED"
    assert report["reproduced"] is True
    assert "induced failure" in report["output"]


def test_replay_capsule_passing_case(tmp_path: Path) -> None:
    test_dir = tmp_path / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_pass.py"
    test_file.write_text(
        "def test_always_passes():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )

    capsule_path = flake_hunter.create_replay_capsule(
        root=tmp_path,
        node_id=str(test_file) + "::test_always_passes",
        prng_seed=999,
    )
    report = flake_hunter.replay_capsule(capsule_path, root=tmp_path)
    assert report["verdict"] == "PASSED"
    assert report["reproduced"] is False


def test_replay_cli_formats_and_out(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    test_dir = tmp_path / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_cli.py"
    test_file.write_text(
        "def test_cli_unit():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    capsule_path = flake_hunter.create_replay_capsule(
        root=tmp_path,
        node_id=str(test_file) + "::test_cli_unit",
    )

    out_file = tmp_path / "replay_out.json"
    summary_file = tmp_path / "summary.md"

    rc = flake_hunter.replay_main(
        [
            str(capsule_path),
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(out_file),
            "--summary-out",
            str(summary_file),
        ]
    )
    assert rc == 0
    assert out_file.is_file()
    assert summary_file.is_file()

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["verdict"] == "PASSED"

    rc_text = flake_hunter.replay_main(
        [
            str(capsule_path),
            "--repo-root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )
    assert rc_text == 0
    captured = capsys.readouterr()
    assert "SDETKit Replay: verdict=PASSED" in captured.out


def test_anti_cheating_tautological_assertion_genome() -> None:
    code = "def test_cheating():\n    x = 10\n    assert x == x\n    assert True\n"
    report = flake_hunter.scan_flake_genome(source_code=code)
    marker_types = [m["type"] for m in report["markers"]]
    assert "TAUTOLOGICAL_ASSERTION" in marker_types


def test_anti_cheating_swallowed_exception_genome() -> None:
    code = (
        "def test_bad_swallowing():\n"
        "    try:\n"
        "        dangerous_call()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    report = flake_hunter.scan_flake_genome(source_code=code)
    marker_types = [m["type"] for m in report["markers"]]
    assert "SWALLOWED_TEST_EXCEPTION" in marker_types


def test_anti_cheating_change_verifier_facts() -> None:
    clean_code = "def test_real():\n    assert compute() == 42\n"
    cheated_code = (
        "def test_real():\n"
        "    try:\n"
        "        compute()\n"
        "    except Exception:\n"
        "        pass\n"
        "    assert True\n"
    )

    clean_facts = change_verifier.test_facts(clean_code, anti_cheating=True)
    assert clean_facts["test_real"]["assertions"] == 1
    assert clean_facts["test_real"]["tautologies"] == 0
    assert clean_facts["test_real"]["swallowed_exceptions"] == 0

    cheated_facts = change_verifier.test_facts(cheated_code, anti_cheating=True)
    assert cheated_facts["test_real"]["assertions"] == 0  # assert True not counted!
    assert cheated_facts["test_real"]["tautologies"] == 1
    assert cheated_facts["test_real"]["swallowed_exceptions"] == 1
