#!/usr/bin/env python3
"""Write a local, report-only utility timing baseline. Not a CI performance gate."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import timeit
from collections.abc import Callable
from pathlib import Path

from sdetkit.utils.atomicio import canonical_json_bytes
from sdetkit.utils.textutil import parse_kv_line


def positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def measure(operation: Callable[[], object], iterations: int, repeats: int) -> dict:
    samples = timeit.repeat(operation, number=iterations, repeat=repeats)
    return {
        "iterations_per_repeat": iterations,
        "repeats": repeats,
        "samples_seconds": samples,
        "median_microseconds_per_call": statistics.median(samples) * 1_000_000 / iterations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/utils-benchmark.json"))
    parser.add_argument("--iterations", type=positive, default=10000)
    parser.add_argument("--repeats", type=positive, default=7)
    args = parser.parse_args()
    line = 'name="two words" count=42 marker=a=b'
    payload = {"z": [True, None], "a": "caf\u00e9"}
    report = {
        "schema": "sdetkit.utils_benchmark.v1",
        "report_only": True,
        "performance_gate": None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "workloads": {"parse_kv_line": line, "canonical_json_bytes": payload},
        "benchmarks": {
            "parse_kv_line": measure(lambda: parse_kv_line(line), args.iterations, args.repeats),
            "canonical_json_bytes": measure(
                lambda: canonical_json_bytes(payload), args.iterations, args.repeats
            ),
        },
        "caveat": "Local timing samples only. Compare the same workload, runtime and machine; no speedup or regression is inferred.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
