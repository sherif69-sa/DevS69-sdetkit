"""`sdetkit verify flake`: hunt flaky tests, prove non-determinism, and measure variance."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit.gates.project_env import resolve_project_python

JsonObject = dict[str, Any]

DEFAULT_FLAKE_RUNS = 5
DEFAULT_PER_RUN_TIMEOUT = 60

# Regex patterns to detect failure causes and test ids from pytest output
_FAILED_TEST_RE = re.compile(r"FAILED\s+([^\s:]+(?:::[^\s:]+)+)")
_ERROR_TEST_RE = re.compile(r"ERROR\s+([^\s:]+(?:::[^\s:]+)+)")

_RACE_KEYWORDS = (
    "timeout",
    "timed out",
    "deadline",
    "asyncio.exceptions.timeouterror",
    "timeouterror",
    "wait",
    "event not set",
)
_STATE_KEYWORDS = (
    "already exists",
    "duplicate",
    "address in use",
    "fileexistserror",
    "mock not called",
    "singleton",
    "fixture",
)


def _classify_cause(output: str) -> str:
    lower = output.lower()
    if any(k in lower for k in _RACE_KEYWORDS):
        return "TIMING_RACE"
    if any(k in lower for k in _STATE_KEYWORDS):
        return "STATE_POLLUTION"
    return "UNKNOWN"


def _extract_failures(stdout: str, stderr: str) -> list[str]:
    combined = f"{stdout}\n{stderr}"
    found: list[str] = []
    for match in _FAILED_TEST_RE.finditer(combined):
        test_id = match.group(1).strip()
        if test_id not in found:
            found.append(test_id)
    for match in _ERROR_TEST_RE.finditer(combined):
        test_id = match.group(1).strip()
        if test_id not in found:
            found.append(test_id)
    return found


def _compute_stats(durations: list[float]) -> dict[str, float]:
    if not durations:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "stddev": 0.0}
    n = len(durations)
    mean_val = sum(durations) / n
    variance = sum((x - mean_val) ** 2 for x in durations) / n if n > 1 else 0.0
    return {
        "min": round(min(durations), 4),
        "max": round(max(durations), 4),
        "mean": round(mean_val, 4),
        "stddev": round(math.sqrt(variance), 4),
    }


def _run_single_test_iteration(
    executable: str,
    args: list[str],
    *,
    cwd: Path,
    timeout: int,
    env_overrides: Mapping[str, str] | None = None,
) -> tuple[bool, float, str, str]:
    env = {
        k: v for k, v in os.environ.items() if k not in ("PYTEST_ADDOPTS", "PYTEST_XDIST_WORKER")
    }
    if env_overrides:
        env.update(env_overrides)

    cmd = [executable, "-m", "pytest", "-o", "addopts=", "-q", "--tb=short", *args]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        duration = time.monotonic() - t0
        return proc.returncode == 0, duration, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return False, duration, "", "test execution timed out"
    except OSError as err:
        duration = time.monotonic() - t0
        return False, duration, "", f"execution error: {err}"


def hunt_flakes(
    root: Path,
    target: str | Path | None = None,
    *,
    runs: int = DEFAULT_FLAKE_RUNS,
    shuffle: bool = True,
    seed: int | None = None,
    timeout: int = DEFAULT_PER_RUN_TIMEOUT,
    max_seconds: float | None = None,
    fail_fast: bool = False,
    extra_args: Sequence[str] = (),
) -> JsonObject:
    """Stress-test test targets over multiple iterations to detect and prove non-determinism."""

    target_args: list[str] = []
    if target:
        target_str = str(target)
        target_args.append(target_str)
    if extra_args:
        target_args.extend(extra_args)

    env = resolve_project_python(root)
    total_runs = max(2, min(runs, 100))
    rng = random.Random(seed if seed is not None else 42)

    durations: list[float] = []
    run_records: list[JsonObject] = []
    all_failing_tests: set[str] = set()
    start_time = time.monotonic()

    passed_count = 0
    failed_count = 0

    for iteration in range(1, total_runs + 1):
        if max_seconds is not None and (time.monotonic() - start_time) > max_seconds:
            break

        current_seed = rng.randint(1, 1_000_000) if shuffle else (seed or 0)
        iter_env = {"PYTHONHASHSEED": str(current_seed)}

        passed, duration, out, err = _run_single_test_iteration(
            env.executable,
            target_args,
            cwd=root,
            timeout=timeout,
            env_overrides=iter_env,
        )
        durations.append(duration)

        failed_tests = _extract_failures(out, err)
        record: JsonObject = {
            "run": iteration,
            "passed": passed,
            "duration": round(duration, 4),
            "seed": current_seed,
            "failed_tests": failed_tests,
        }

        if passed:
            passed_count += 1
        else:
            failed_count += 1
            cause = _classify_cause(f"{out}\n{err}")
            record["cause"] = cause
            record["error_snippet"] = (err.strip() or out.strip())[-500:]
            all_failing_tests.update(failed_tests)

        run_records.append(record)

        if fail_fast and failed_count > 0 and passed_count > 0:
            break

    completed = len(run_records)
    if completed == 0:
        return {
            "ok": True,
            "verdict": "not_run",
            "reason": "no runs completed within time limit",
            "runs_planned": total_runs,
            "runs_completed": 0,
            "passed_runs": 0,
            "failed_runs": 0,
            "flake_rate": 0.0,
            "duration_stats": _compute_stats([]),
            "flaky_tests": [],
            "failures": [],
            "reasons": ["no runs completed"],
        }

    # If it failed some runs and passed other runs: PROVEN FLAKY!
    if passed_count > 0 and failed_count > 0:
        verdict = "flaky"
        ok = False
        flaky_tests = sorted(all_failing_tests) or [str(target or "test suite")]
        flake_rate = round((failed_count / completed) * 100.0, 1)
        reasons = [
            f"test non-determinism proven: {failed_count}/{completed} runs failed ({flake_rate}% flake rate)"
        ]
    elif failed_count == completed:
        verdict = "broken"
        ok = False
        flaky_tests = []
        flake_rate = 100.0
        reasons = [f"test consistently broken: failed all {completed} runs"]
    else:
        verdict = "deterministic"
        ok = True
        flaky_tests = []
        flake_rate = 0.0
        reasons = [f"deterministic: passed all {completed} runs"]

    return {
        "ok": ok,
        "verdict": verdict,
        "target": str(target) if target else "all",
        "runs_planned": total_runs,
        "runs_completed": completed,
        "passed_runs": passed_count,
        "failed_runs": failed_count,
        "flake_rate": flake_rate,
        "duration_stats": _compute_stats(durations),
        "flaky_tests": flaky_tests,
        "failures": [r for r in run_records if not r.get("passed", True)],
        "runs": run_records,
        "reasons": reasons,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    verdict = payload.get("verdict", "unknown")
    completed = payload.get("runs_completed", 0)
    passed = payload.get("passed_runs", 0)
    failed = payload.get("failed_runs", 0)
    rate = payload.get("flake_rate", 0.0)
    stats = payload.get("duration_stats", {})
    target = payload.get("target", "all")

    if verdict == "deterministic":
        badge = "DETERMINISTIC PASS"
        symbol = "[OK]"
    elif verdict == "flaky":
        badge = "FLAKY (PROVEN NON-DETERMINISTIC)"
        symbol = "[FLAKE]"
    elif verdict == "broken":
        badge = "BROKEN (100% FAILURE)"
        symbol = "[FAIL]"
    else:
        badge = "NOT RUN"
        symbol = "[SKIP]"

    lines: list[str] = [
        f"### {symbol} Flake Hunter: {badge}",
        "",
        f"- **Target:** `{target}`",
        f"- **Completed Runs:** {completed} ({passed} passed, {failed} failed)",
        f"- **Flake Rate:** {rate}%",
        f"- **Duration:** min={stats.get('min', 0)}s, max={stats.get('max', 0)}s, mean={stats.get('mean', 0)}s, stddev={stats.get('stddev', 0)}s",
        "",
    ]

    flaky_tests = payload.get("flaky_tests", [])
    if flaky_tests:
        lines.append("#### Flaky Tests Detected")
        for test in flaky_tests:
            lines.append(f"- ` {test} `")
        lines.append("")

    failures = payload.get("failures", [])
    if failures:
        lines.append("#### Failure Log Details")
        for failure in failures[:5]:
            run_no = failure.get("run")
            cause = failure.get("cause", "UNKNOWN")
            snippet = failure.get("error_snippet", "").strip()
            lines.append(f"- **Run #{run_no}** (cause: `{cause}`):")
            if snippet:
                lines.append(f"  ```text\n  {snippet[:200]}\n  ```")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit verify flake",
        description="Hunt flaky tests, prove test non-determinism, and measure duration variance.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target test path or test id (e.g. tests/test_api.py::test_case)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_FLAKE_RUNS,
        help=f"Number of test iterations to execute (default: {DEFAULT_FLAKE_RUNS})",
    )
    parser.add_argument(
        "--no-shuffle",
        action="store_true",
        help="Disable execution order / hash seed randomization",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Fixed seed for reproducible test shuffling",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_PER_RUN_TIMEOUT,
        help=f"Per-run timeout in seconds (default: {DEFAULT_PER_RUN_TIMEOUT})",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Maximum total runtime budget in seconds",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first non-deterministic pass/fail split",
    )
    parser.add_argument(
        "--format",
        choices=["md", "json", "text"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write JSON payload to a file",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Extra arguments passed to test runner",
    )

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    payload = hunt_flakes(
        root=root,
        target=args.target,
        runs=args.runs,
        shuffle=not args.no_shuffle,
        seed=args.seed,
        timeout=args.timeout,
        max_seconds=args.max_seconds,
        fail_fast=args.fail_fast,
        extra_args=args.extra_args,
    )

    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    elif args.format == "text":
        verdict = payload.get("verdict", "unknown")
        rate = payload.get("flake_rate", 0.0)
        print(f"verdict={verdict} flake_rate={rate}% runs={payload.get('runs_completed')}")
    else:
        print(render_markdown(payload))

    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
