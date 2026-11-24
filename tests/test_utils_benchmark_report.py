from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/benchmark_utils.py"
spec = importlib.util.spec_from_file_location("utils_benchmark", SCRIPT)
assert spec is not None and spec.loader is not None
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_measure_preserves_samples_and_uses_median_per_operation(monkeypatch):
    def operation():
        return "payload"

    def fake_repeat(function, *, number, repeat):
        assert function is operation
        assert (number, repeat) == (100, 3)
        return [0.01, 0.04, 0.02]

    monkeypatch.setattr(benchmark.timeit, "repeat", fake_repeat)
    report = benchmark.measure(operation, 100, 3)
    assert report == {
        "iterations_per_repeat": 100,
        "repeats": 3,
        "samples_seconds": [0.01, 0.04, 0.02],
        "median_microseconds_per_call": 200.0,
    }


@pytest.mark.parametrize("flag", ["--iterations", "--repeats"])
@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_cli_rejects_invalid_sample_counts(monkeypatch, flag, value):
    monkeypatch.setattr("sys.argv", [str(SCRIPT), flag, value])
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2


def test_cli_runs_real_workloads_and_writes_report_only_baseline(tmp_path, monkeypatch, capsys):
    out = tmp_path / "nested" / "benchmark.json"
    monkeypatch.setattr(
        "sys.argv", [str(SCRIPT), "--out", str(out), "--iterations", "2", "--repeats", "3"]
    )
    assert benchmark.main() == 0
    report = json.loads(out.read_text())
    assert json.loads(capsys.readouterr().out) == report
    assert report["schema"] == "sdetkit.utils_benchmark.v1"
    assert report["report_only"] is True
    assert report["performance_gate"] is None
    assert report["python"] and report["platform"] and report["caveat"]
    assert (
        set(report["workloads"])
        == set(report["benchmarks"])
        == {"parse_kv_line", "canonical_json_bytes"}
    )
    for result in report["benchmarks"].values():
        assert result["iterations_per_repeat"] == 2
        assert result["repeats"] == 3
        assert len(result["samples_seconds"]) == 3
        assert all(value >= 0 for value in result["samples_seconds"])
        assert result["median_microseconds_per_call"] >= 0


def test_cli_entrypoint_runs_as_subprocess_and_writes_report(tmp_path):
    out = tmp_path / "nested" / "benchmark.json"
    repo_root = SCRIPT.parents[1]
    env = os.environ.copy()
    pythonpath = [str(repo_root / "src")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(out),
            "--iterations",
            "2",
            "--repeats",
            "1",
        ],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(out.read_text(encoding="utf-8"))
    assert json.loads(completed.stdout) == report
    assert report["schema"] == "sdetkit.utils_benchmark.v1"
    assert report["report_only"] is True
    assert report["performance_gate"] is None
