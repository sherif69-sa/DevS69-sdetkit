#!/usr/bin/env python3
"""Run a bounded, report-only mutation pilot in an isolated copy."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODULES = ("textutil", "atomicio")
TEST_FILES = (
    "test_textutil.py",
    "test_atomicio.py",
    "test_atomicio_bytes_branches_wave1.py",
    "test_utils_contracts.py",
)

TARGETS = {
    "textutil": (("src/sdetkit/utils/textutil.py",), TEST_FILES),
    "atomicio": (("src/sdetkit/utils/atomicio.py",), TEST_FILES),
    "kvcli": (
        ("src/sdetkit/kvcli.py",),
        ("test_kvcli_mutmut_killers.py", "test_kvcli_entry_contracts.py"),
    ),
    "cli": (
        ("src/sdetkit/cli/__init__.py",),
        (
            "test_cli_sdetkit.py",
            "test_entrypoints_smoke.py",
            "test_cli_smoke_coverage.py",
            "test_cli_dispatch.py",
            "test_cli_parser_artifact_contracts.py",
        ),
    ),
}


def select_scope(target: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if target is None:
        return tuple(f"src/sdetkit/utils/{name}.py" for name in MODULES), TEST_FILES
    return TARGETS[target]


def summarize(stats: dict | None, baseline: int, run: int) -> dict:
    """Never turn missing evidence or a tool failure into a passing score."""
    status = "completed"
    if baseline:
        status = "baseline_failed"
    elif stats is None or run != 0:
        status = "tool_error"
    elif not stats.get("total", 0):
        status = "no_mutants"
    return {
        "status": status,
        "baseline_exit": baseline,
        "mutation_exit": run,
        "counts": stats,
        "report_only": True,
        "score_gate": None,
    }


def command(args: list[str], cwd: Path, log: Path, timeout: int) -> int:
    with log.open("w") as stream:
        try:
            return subprocess.run(
                args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False
            ).returncode
        except subprocess.TimeoutExpired:
            stream.write("\nPilot command exceeded its time budget.\n")
            return 124


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/mutation-pilot"))
    parser.add_argument("--target", choices=tuple(TARGETS))
    args = parser.parse_args()
    source_files, test_files = select_scope(args.target)
    root = Path(__file__).resolve().parents[1]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sdetkit-mutation-") as temp:
        work = Path(temp)
        shutil.copytree(root / "src", work / "src")
        (work / "tests").mkdir()
        for name in test_files:
            shutil.copy2(root / "tests" / name, work / "tests")
        # Use the current mutmut 3 configuration, not removed CLI flags.
        (work / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["src"]\n'
            + "only_mutate = "
            + json.dumps(source_files)
            + "\n"
            + 'pytest_add_cli_args = ["-q", "-x"]\n'
            + 'pytest_add_cli_args_test_selection = ["tests"]\n',
            encoding="utf-8",
        )
        os.environ["PYTHONPATH"] = str(work / "src")
        baseline = command(
            [sys.executable, "-m", "pytest", "-q", "tests"], work, out / "baseline.log", 120
        )
        run = 1
        stats = None
        if baseline == 0:
            run = command(
                [sys.executable, "-m", "mutmut", "run", "--max-children", "2"],
                work,
                out / "mutation.log",
                600,
            )
            command([sys.executable, "-m", "mutmut", "results"], work, out / "results.log", 60)
            command(
                [sys.executable, "-m", "mutmut", "export-cicd-stats"], work, out / "export.log", 60
            )
            stats_path = work / "mutants/mutmut-cicd-stats.json"
            if stats_path.exists():
                stats = json.loads(stats_path.read_text(encoding="utf-8"))
        report = summarize(stats, baseline, run)
        report["modules"] = list(source_files)
        report["test_scope"] = [f"tests/{name}" for name in test_files]
        report["caveat"] = (
            "Focused isolated suite, not whole-repo proof. No-test mutants require investigation. Timeouts are not counted as killed."
        )
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        summary = "# Mutation pilot (report-only)\n\n" + f"Status: {report['status']}\n\n"
        summary += "```json\n" + json.dumps(report, indent=2) + "\n```\n"
        (out / "summary.md").write_text(summary, encoding="utf-8")
        print(summary)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
