from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mutation_pilot.py"
spec = importlib.util.spec_from_file_location("mutation_pilot", SCRIPT)
assert spec is not None and spec.loader is not None
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_missing_evidence_is_not_a_score():
    assert pilot.summarize(None, 0, 0)["status"] == "tool_error"
    assert pilot.summarize({"total": 0}, 0, 0)["status"] == "no_mutants"


def test_baseline_and_runner_errors_are_explicit():
    assert pilot.summarize({"total": 2}, 1, 0)["status"] == "baseline_failed"
    assert pilot.summarize({"total": 2}, 0, 124)["status"] == "tool_error"


def test_survivors_and_no_tests_are_preserved_without_gate():
    stats = {"total": 10, "killed": 4, "survived": 3, "no_tests": 2, "timeout": 1}
    report = pilot.summarize(stats, 0, 0)
    assert report["status"] == "completed"
    assert report["counts"] == stats
    assert report["report_only"] is True
    assert report["score_gate"] is None


def test_scope_is_exactly_two_modules():
    assert pilot.MODULES == ("textutil", "atomicio")


def test_scope_includes_existing_byte_tests_and_new_contracts():
    assert pilot.TEST_FILES == (
        "test_textutil.py",
        "test_atomicio.py",
        "test_atomicio_bytes_branches_wave1.py",
        "test_utils_contracts.py",
    )
    assert all((SCRIPT.parents[1] / "tests" / name).is_file() for name in pilot.TEST_FILES)
