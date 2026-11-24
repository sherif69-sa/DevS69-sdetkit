from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

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
        "test_atomicio_mutmut_killers.py",
        "test_atomicio_bytes_branches_wave1.py",
        "test_utils_contracts.py",
    )
    assert all((SCRIPT.parents[1] / "tests" / name).is_file() for name in pilot.TEST_FILES)


def test_default_scope_is_unchanged():
    sources, tests = pilot.select_scope(None)
    assert sources == ("src/sdetkit/utils/textutil.py", "src/sdetkit/utils/atomicio.py")
    assert tests == pilot.TEST_FILES


def test_legacy_targets_use_real_implementations_and_in_process_tests():
    assert set(pilot.TARGETS) == {"textutil", "atomicio", "kvcli", "cli"}
    for target in pilot.TARGETS:
        sources, tests = pilot.select_scope(target)
        assert sources and tests
        assert all((SCRIPT.parents[1] / name).is_file() for name in sources)
        assert all((SCRIPT.parents[1] / "tests" / name).is_file() for name in tests)
    assert pilot.select_scope("cli")[0] == ("src/sdetkit/cli/__init__.py",)
    assert "test_kvcli.py" not in pilot.select_scope("kvcli")[1]


def test_legacy_workflow_does_not_hide_obsolete_runner_failures():
    text = (SCRIPT.parents[1] / ".github/workflows/mutation-tests.yml").read_text()
    assert "--paths-to-mutate" not in text
    assert "mutmut html" not in text
    assert "mutmut results || true" not in text
    assert 'python scripts/mutation_pilot.py --target "$target"' in text
    assert 'exit "$failed"' in text
    assert "targets=(textutil atomicio kvcli cli)" in text


def test_cli_scope_includes_existing_in_process_dispatch_contracts():
    assert "test_cli_dispatch.py" in pilot.select_scope("cli")[1]
    assert "test_cli_parser_artifact_contracts.py" in pilot.select_scope("cli")[1]
    # These subprocess tests force PYTHONPATH to the unmutated source tree.
    assert "test_doctor_report_cli_contract.py" not in pilot.select_scope("cli")[1]


@pytest.mark.parametrize(
    "stats",
    [
        {},
        {"total": -1},
        {"total": True},
        {"total": "2"},
        {"total": 2, "killed": 3},
        {"total": 2, "killed": 1},
        {"total": 2, "killed": -1, "survived": 3},
        {"total": 2, "killed": 1.0, "survived": 1},
        {"total": 2, "killed": True, "survived": 1},
        {"total": 2, "killed": 1, "check_was_interrupted_by_user": 1},
    ],
)
def test_inconsistent_or_interrupted_counts_are_tool_errors(stats):
    report = pilot.summarize(stats, 0, 0)
    assert report["status"] == "tool_error"
    assert report["counts"] == stats


def test_export_error_is_not_a_completed_score():
    report = pilot.summarize({"total": 2, "killed": 2}, 0, 0, 1)
    assert report["status"] == "tool_error"
    assert report["export_exit"] == 1


@pytest.mark.parametrize("text", ["not json", "[]", "null", "42", "true", '"text"'])
def test_invalid_export_is_missing_evidence(tmp_path, text):
    path = tmp_path / "stats.json"
    path.write_text(text, encoding="utf-8")
    assert pilot.load_stats(path) is None
    assert pilot.summarize(pilot.load_stats(path), 0, 0)["status"] == "tool_error"


def test_missing_export_is_missing_evidence(tmp_path):
    assert pilot.load_stats(tmp_path / "missing.json") is None


def test_valid_export_preserves_every_outcome(tmp_path):
    import json

    stats = {key: 1 for key in pilot.COUNT_FIELDS}
    stats["check_was_interrupted_by_user"] = 0
    stats["total"] = sum(stats.values())
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(stats), encoding="utf-8")
    report = pilot.summarize(pilot.load_stats(path), 0, 0)
    assert report["status"] == "completed"
    assert report["counts"] == stats


@pytest.mark.parametrize("previous", [None, "", "existing-pythonpath"])
@pytest.mark.parametrize("baseline", [0, 1])
def test_main_isolates_pythonpath_and_writes_report(monkeypatch, tmp_path, previous, baseline):
    import json
    import os

    if previous is None:
        monkeypatch.delenv("PYTHONPATH", raising=False)
    else:
        monkeypatch.setenv("PYTHONPATH", previous)
    out = tmp_path / "report"
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "--target", "textutil", "--out", str(out)])
    calls = []

    def fake_command(args, cwd, log, timeout, **kwargs):
        calls.append((args, cwd, log, timeout, kwargs))
        if "pytest" in args:
            return baseline
        if "export-cicd-stats" in args:
            stats_path = cwd / "mutants" / "mutmut-cicd-stats.json"
            stats_path.parent.mkdir()
            stats_path.write_text(json.dumps({"total": 2, "killed": 1, "survived": 1}))
        return 0

    monkeypatch.setattr(pilot, "command", fake_command)
    assert pilot.main() == baseline
    assert os.environ.get("PYTHONPATH") == previous
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == ("baseline_failed" if baseline else "completed")
    assert report["modules"] == ["src/sdetkit/utils/textutil.py"]
    assert report["report_only"] is True
    assert report["score_gate"] is None
    assert report["test_scope"] == [f"tests/{name}" for name in pilot.TEST_FILES]
    assert report["status"] in (out / "summary.md").read_text()
    assert len(calls) == (1 if baseline else 4)
    for _args, work, log, _timeout, kwargs in calls:
        assert not work.exists()
        assert log.parent == out
        assert kwargs["env"]["PYTHONPATH"] == str(work / "src")


@pytest.mark.parametrize("timeout", [False, True])
def test_command_forwards_isolated_environment_and_records_timeout(monkeypatch, tmp_path, timeout):
    import subprocess

    env = {"PYTHONPATH": "isolated-source"}
    log = tmp_path / "command.log"

    def fake_run(args, **kwargs):
        assert args == ["test-command"]
        assert kwargs["cwd"] == tmp_path
        assert kwargs["env"] is env
        assert kwargs["timeout"] == 7
        assert kwargs["check"] is False
        assert kwargs["stderr"] == subprocess.STDOUT
        kwargs["stdout"].write("command output\n")
        if timeout:
            raise subprocess.TimeoutExpired(args, 7)
        return subprocess.CompletedProcess(args, 3)

    monkeypatch.setattr(pilot.subprocess, "run", fake_run)
    assert pilot.command(["test-command"], tmp_path, log, 7, env=env) == (124 if timeout else 3)
    assert log.read_text().startswith("command output\n")
    assert ("exceeded its time budget" in log.read_text()) is timeout


def test_atomic_scope_retains_existing_in_process_mutation_killers():
    for target in (None, "textutil", "atomicio"):
        assert "test_atomicio_mutmut_killers.py" in pilot.select_scope(target)[1]


def test_repository_mutmut_config_uses_supported_keys_without_changing_scope():
    import tomllib

    config = tomllib.loads((SCRIPT.parents[1] / "pyproject.toml").read_text())["tool"]["mutmut"]
    assert config["source_paths"] == ["src/sdetkit"]
    assert config["pytest_add_cli_args_test_selection"] == ["tests"]
    assert config["pytest_add_cli_args"] == ["-q", "--ignore=mutants"]
    assert not {"paths_to_mutate", "tests_dir", "runner"} & config.keys()


@pytest.mark.parametrize(
    "error", [FileNotFoundError("missing executable"), PermissionError("denied")]
)
def test_command_launch_failure_is_logged_instead_of_crashing(tmp_path, monkeypatch, error):
    def fail_launch(*args, **kwargs):
        raise error

    monkeypatch.setattr(pilot.subprocess, "run", fail_launch)
    log = tmp_path / "launch.log"
    assert pilot.command(["missing-command"], tmp_path, log, 1) == 127
    assert "could not start" in log.read_text()
    assert str(error) in log.read_text()
